from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from test_teaching import env
from app.core import rate_limit as limiter
from app.core.security import hash_password
from app.models.academic import Score
from app.models.subscription import Subscription, SubscriptionPayment, BillingNotice
from app.models.user import UserRole
from app.models.institution import InstitutionType
from app.services.subscriptions import subscription_view, kenya_today
from app.services.billing_reminders import send_billing_reminders


@pytest.fixture(autouse=True)
def rate_limit_stub(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, 'incr', lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, 'expire', lambda *args: True)


def platform(env):
    user = env['user']('owner', UserRole.PLATFORM_ADMIN)
    user.institution_id = None
    env['db'].commit()
    return user


def subscription(env, **changes):
    row = Subscription(institution_id=env['cls'].institution_id, monthly_fee=Decimal('2500'), grace_days=5,
        enforcement_enabled=True, next_due_date=kenya_today(), support_email='support@example.test', **changes)
    env['db'].add(row); env['db'].commit()
    return row


def test_email_less_creation_and_unique_id_login(env):
    c = env['as_user'](env['admin'])
    root = f"/api/teaching/classes/{env['cls'].id}/students"
    body = dict(first_name='New', last_name='Pupil', admission_number='ADM-2', login_method='STUDENT_ID', login_id='school-002')
    assert env['as_user'](env['supervisor']).post(root, json=body).status_code == 403
    c = env['as_user'](env['admin'])
    created = c.post(root, json=body)
    assert created.status_code == 201, created.text
    data = created.json()
    assert data['login_identity'] == 'SCHOOL-002' and data['student']['email'] is None
    assert c.post(root, json={**body, 'admission_number': 'ADM-3', 'login_id': 'SCHOOL-002'}).status_code == 409
    credentials = dict(student_id='school-002', password=data['temporary_password'])
    assert c.post('/api/auth/student/login', json=credentials).status_code == 200
    assert c.get('/api/student/subjects').status_code == 403  # first-login password gate
    assert c.post('/api/auth/teacher/login', json=credentials).status_code == 422
    assert c.post('/api/auth/student/login', json={**credentials, 'email': 'a@example.test'}).status_code == 422
    assert c.post('/api/auth/student/login', json={**credentials, 'password': 'wrong'}).status_code == 401


def test_student_login_method_enforced_and_id_case_unique(env):
    user = env['pupil']
    user.student_login_method = 'STUDENT_ID'; user.student_login_id = 'ID-1'
    user.password_hash = hash_password('Student-password-123!')
    env['db'].commit()
    c = env['client']
    assert c.post('/api/auth/student/login', json=dict(email=user.email, password='Student-password-123!')).status_code == 401
    assert c.post('/api/auth/student/login', json=dict(student_id='id-1', password='Student-password-123!')).status_code == 200
    other = env['other_pupil']; other.student_login_method = 'STUDENT_ID'; other.student_login_id = 'ID-1'
    with pytest.raises(IntegrityError): env['db'].commit()
    env['db'].rollback()


@pytest.mark.parametrize('body', [dict(login_method='EMAIL'), dict(login_method='STUDENT_ID'), dict(login_method='STUDENT_ID', login_id='has spaces'), dict(login_method='OTHER', email='a@example.test')])
def test_invalid_student_access_rejected(env, body):
    url = f"/api/institution/students/{env['pupil'].id}/login"
    assert env['as_user'](env['admin']).put(url, json=body).status_code == 422


def test_admin_access_changes_revoke_sessions_and_reset_without_email(env):
    pupil = env['pupil']; c = env['as_user'](pupil)
    old_cookie = c.cookies.get('access_token')
    url = f'/api/institution/students/{pupil.id}'
    assert env['as_user'](env['teacher']).put(url + '/login', json=dict(login_method='STUDENT_ID', login_id='NEW-ID')).status_code == 403
    assert env['as_user'](env['admin']).put(url + '/login', json=dict(login_method='STUDENT_ID', login_id='NEW-ID')).status_code == 200
    found = env['as_user'](env['admin']).get('/api/institution/users?search=NEW-ID').json()
    assert found['total'] == 1 and found['items'][0]['student_login_id'] == 'NEW-ID'
    c.cookies.set('access_token', old_cookie)
    assert c.get('/api/me').status_code == 401
    c = env['as_user'](env['admin'])
    other = f"/api/institution/students/{env['other_pupil'].id}/reset-password"
    assert c.post(other).status_code == 404
    result = c.post(url + '/reset-password')
    assert result.status_code == 200 and result.json()['login_identity'] == 'NEW-ID'
    assert c.post('/api/auth/student/login', json=dict(student_id='NEW-ID', password=result.json()['temporary_password'])).json()['must_change_password']


def test_new_sessions_after_reset_keep_subsecond_issue_time(env, monkeypatch):
    from datetime import datetime, timezone
    from app.core import security
    changed = datetime.now(timezone.utc).replace(microsecond=500000)
    env['pupil'].password_changed_at = changed
    env['db'].commit()
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return changed + timedelta(microseconds=100)
    monkeypatch.setattr(security, 'datetime', Clock)
    c = env['as_user'](env['pupil'])
    token = security.decode_token(c.cookies.get('access_token'))
    assert isinstance(token['iat'], float)
    assert c.get('/api/me').status_code == 200


def test_directory_and_teacher_dashboard_are_scoped(env):
    own = env['as_user'](env['teacher']).get('/api/teaching/overview').json()
    assert own['enrollment_by_class'] == [{'name': 'Form 1 · 2026', 'students': 1}]
    assert env['as_user'](env['unrelated']).get('/api/teaching/overview').json()['enrollment_by_class'] == []
    assert env['as_user'](env['admin']).get('/api/platform/institution-directory').status_code == 403
    owner = platform(env)
    c = env['as_user'](owner)
    result = c.get('/api/platform/institution-directory?search=School&limit=1').json()
    assert result['total'] == 2 and len(result['items']) == 1
    assert c.get('/api/platform/institution-directory?search=%25').json()['total'] == 0
    assert c.get('/api/platform/institution-directory?limit=101').status_code == 422


def test_results_withheld_then_released_and_supervisor_can_view_all_marks(env):
    work = env['work']; work.published = True
    env['db'].add(Score(institution_id=work.institution_id, coursework_id=work.id, student_id=env['student'].id, score=18, feedback='Private feedback'))
    env['db'].commit()
    url = f'/api/teaching/coursework/{work.id}/results-release'
    for path in ['/api/student/assignments', '/api/student/coursework']:
        result = env['as_user'](env['pupil']).get(path).json()[0]
        assert result['score'] is None and result['feedback'] == ''
    report = f"/api/teaching/classes/{env['cls'].id}/report"
    for who in ['teacher', 'unrelated', 'outsider']:
        assert env['as_user'](env[who]).get(report).status_code == 404
    data = env['as_user'](env['supervisor']).get(report).json()
    assert data['students'][0]['marks'][0]['score'] == 18
    assert env['as_user'](env['supervisor']).put(url, json={'released': True}).status_code == 404
    assert env['as_user'](env['teacher']).put(url, json={'released': True}).status_code == 200
    assert env['as_user'](env['pupil']).get('/api/student/assignments').json()[0]['feedback'] == 'Private feedback'
    assert env['as_user'](env['teacher']).put(url, json={'released': False}).status_code == 200
    assert env['as_user'](env['pupil']).get('/api/student/assignments').json()[0]['score'] is None


def test_learning_settings_are_tenant_specific_and_grading_is_explicit(env):
    env['institutions'][0].type = InstitutionType.UNIVERSITY
    env['db'].commit()
    url = '/api/institution/learning-settings'
    assert env['as_user'](env['pupil']).get(url).json()['teacher_label'] == 'Lecturer'
    settings = env['as_user'](env['admin']).get(url).json()
    settings['grade_bands'] = [{'minimum': 0, 'label': 'Needs support'}, {'minimum': 80, 'label': 'Excellent'}]
    assert env['as_user'](env['teacher']).put(url, json=settings).status_code == 403
    assert env['as_user'](env['admin']).put(url, json=settings).status_code == 200
    assert env['as_user'](env['other_pupil']).get(url).json()['grade_bands'] == []
    bad = {**settings, 'grade_bands': [{'minimum': 10, 'label': 'Invalid'}]}
    assert env['as_user'](env['admin']).put(url, json=bad).status_code == 422
    env['work'].published = True; env['work'].grades_released = True
    env['db'].add(Score(institution_id=env['cls'].institution_id, coursework_id=env['work'].id, student_id=env['student'].id, score=18))
    env['db'].commit()
    assert env['as_user'](env['pupil']).get('/api/student/assignments').json()[0]['grade'] == 'Excellent'


def test_freeze_deadline_boundaries(env):
    row = subscription(env)
    due = row.next_due_date
    assert subscription_view(row, due - timedelta(days=1))['status'] == 'CURRENT'
    assert subscription_view(row, due)['status'] == 'GRACE'
    assert not subscription_view(row, due + timedelta(days=4))['frozen']
    assert subscription_view(row, due + timedelta(days=5))['frozen']
    row.enforcement_enabled = False
    assert not subscription_view(row, due + timedelta(days=50))['frozen']
    row.manually_frozen = True
    assert subscription_view(row, due)['frozen']


def test_freeze_blocks_login_sessions_and_regular_workspace_not_owner(env):
    row = subscription(env)
    c = env['as_user'](env['teacher'])
    assert c.get('/api/teaching/classes').status_code == 200
    row.manually_frozen = True; env['db'].commit()
    assert c.get('/api/teaching/classes').status_code == 403
    assert c.get('/api/institution/subscription').json()['frozen']
    assert 'payments' not in c.get('/api/institution/subscription').json()
    env['teacher'].password_hash = hash_password('Valid-password-123!'); env['db'].commit()
    assert c.post('/api/auth/teacher/login', json=dict(email=env['teacher'].email, password='Valid-password-123!')).status_code == 403
    owner = platform(env)
    c = env['as_user'](owner)
    result = c.post('/api/workspace-access/start', json={'target_user_id': str(env['teacher'].id)})
    assert result.status_code == 200
    c.headers['X-Workspace-Token'] = result.json()['token']
    assert c.get('/api/teaching/classes').status_code == 200


def test_payment_and_configuration_platform_only_and_atomic(env):
    owner = platform(env)
    root = f"/api/platform/institutions/{env['cls'].institution_id}"
    body = dict(monthly_fee='2500', next_due_date=str(kenya_today() - timedelta(days=10)), grace_days=5,
                enforcement_enabled=True, support_email='support@example.test')
    assert env['as_user'](env['admin']).put(root + '/subscription', json=body).status_code == 403
    c = env['as_user'](owner)
    assert c.put(root + '/subscription', json=body).json()['frozen']
    assert c.get('/api/platform/subscription-summary').json()['subscription_status']['FROZEN'] == 1
    due = body['next_due_date']
    payment = dict(amount='2500', reference='TXN-001', paid_on=str(kenya_today()), expected_due_date=due, next_due_date=str(kenya_today() + timedelta(days=20)))
    assert c.post(root + '/payments', json={**payment, 'expected_due_date': None}).status_code == 409
    result = c.post(root + '/payments', json=payment)
    assert result.status_code == 201 and not result.json()['frozen']
    summary = c.get('/api/platform/subscription-summary').json()
    assert summary['subscription_status']['CURRENT'] == 1 and summary['payments_recorded_this_month'] == 2500
    assert c.post(root + '/payments', json=payment).status_code == 409
    assert c.put(root + '/subscription', json=body).status_code == 409
    assert env['db'].query(SubscriptionPayment).count() == 1
    detail = c.get(root + '/detail?role=STUDENT').json()
    assert len(detail['users']['items']) == 1 and detail['users']['items'][0]['id'] == str(env['pupil'].id)
    assert detail['billing']['payments'][0]['reference'] == 'TXN-001'


def test_reminders_dry_run_deduplication_and_retry(env, monkeypatch):
    from app.services import billing_reminders
    row = subscription(env)
    env['institutions'][0].official_email = 'office@example.test'; env['db'].commit()
    deliveries = []
    monkeypatch.setattr(billing_reminders, 'send_email', lambda **kwargs: deliveries.append(kwargs))
    assert send_billing_reminders(env['db'])['due'] == 1 and not deliveries
    assert send_billing_reminders(env['db'], deliver=True)['sent'] == 1
    assert send_billing_reminders(env['db'], deliver=True)['sent'] == 0
    assert len(deliveries) == 1 and env['db'].query(BillingNotice).count() == 1
    def failure(**kwargs): raise billing_reminders.EmailSendError('simulated')
    monkeypatch.setattr(billing_reminders, 'send_email', failure)
    later = row.next_due_date + timedelta(days=5)
    assert send_billing_reminders(env['db'], deliver=True, today=later)['failed'] == 1
    assert env['db'].query(BillingNotice).count() == 1
    monkeypatch.setattr(billing_reminders, 'send_email', lambda **kwargs: deliveries.append(kwargs))
    assert send_billing_reminders(env['db'], deliver=True, today=later)['sent'] == 1
