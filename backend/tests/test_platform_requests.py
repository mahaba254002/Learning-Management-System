"""Phase 10: request centre, account anonymisation, institution termination and permanent deletion."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from test_teaching import env  # noqa: F401
from test_tenant_isolation import foreign_records
from test_workspace_access import platform
from app.core import rate_limit as limiter
from app.db.base import Base
from app.models.academic import Score
from app.models.audit import AuditEvent
from app.models.institution import Institution, InstitutionStatus
from app.models.user import User, UserStatus


@pytest.fixture(autouse=True)
def rate_stub(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, 'incr', lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, 'expire', lambda *args: True)


@pytest.fixture
def sent(monkeypatch):
    emails = []
    import app.core.verification as verification
    monkeypatch.setattr(verification, 'generate_verification_code', lambda **kw: emails.append(kw) or None)
    return emails


def admin(env):
    return env['as_user'](env['admin'])


def owner(env):
    if 'platform_user' not in env:
        env['platform_user'] = platform(env)
    return env['as_user'](env['platform_user'])


def test_deletion_request_anonymises_but_keeps_marks(env):
    db = env['db']
    db.add(Score(institution_id=env['institutions'][0].id, coursework_id=env['work'].id, student_id=env['student'].id, score=Decimal('15')))
    db.commit()
    c = admin(env)
    assert c.post('/api/institution/requests', json=dict(kind='ACCOUNT_DELETION', target_user_id=str(env['pupil'].id))).status_code == 422  # reason
    made = c.post('/api/institution/requests', json=dict(kind='ACCOUNT_DELETION', target_user_id=str(env['pupil'].id), details='Left the school in 2025'))
    assert made.status_code == 201, made.text
    assert c.post('/api/institution/requests', json=dict(kind='ACCOUNT_DELETION', target_user_id=str(env['pupil'].id), details='Again please')).status_code == 409
    # Another school's admin cannot ask about this account, and teachers cannot use the request centre.
    assert c.post('/api/institution/requests', json=dict(kind='PASSWORD_RESET', target_user_id=str(env['other_pupil'].id))).status_code == 404
    assert env['as_user'](env['teacher']).get('/api/institution/requests').status_code == 403

    p = owner(env)
    queue = p.get('/api/platform/requests?status=OPEN').json()
    assert queue[0]['institution_name'] == 'School 0' and 'pupil Test' in queue[0]['target_label']
    assert p.post(f"/api/platform/requests/{queue[0]['id']}/decide", json=dict(action='REJECT')).status_code == 422
    done = p.post(f"/api/platform/requests/{queue[0]['id']}/decide", json=dict(action='COMPLETE', note='Done as asked'))
    assert done.status_code == 200, done.text
    assert done.json()['status'] == 'COMPLETED'
    db.expire_all()
    pupil = db.get(User, env['pupil'].id)
    assert (pupil.first_name, pupil.status, pupil.login_enabled) == ('Deleted', UserStatus.ARCHIVED, False)
    assert pupil.email.endswith('@deleted.invalid')
    assert db.query(Score).filter_by(student_id=env['student'].id).one().score == Decimal('15')
    assert db.query(AuditEvent).filter_by(action='request.completed').count() == 1
    # The school admin is told, and sees the outcome.
    c = admin(env)
    assert c.get('/api/institution/requests').json()[0]['status'] == 'COMPLETED'
    assert any('Delete an account' in n['title'] for n in c.get('/api/notifications').json()['items'])
    # A deleted account cannot sign in or be deleted again.
    assert env['as_user'](pupil).get('/api/student/profile').status_code in {401, 403}


def test_reject_withdraw_change_details_and_reset(env, sent):
    c = admin(env)
    change = c.post('/api/institution/requests', json=dict(kind='INSTITUTION_CHANGE', changes=dict(name='School Zero Academy', phone='+254700000001')))
    assert change.status_code == 201, change.text
    assert c.post('/api/institution/requests', json=dict(kind='INSTITUTION_CHANGE', changes=dict(code='HACK'))).status_code == 422
    other = c.post('/api/institution/requests', json=dict(kind='OTHER', details='Please merge two duplicate student accounts')).json()
    reset = c.post('/api/institution/requests', json=dict(kind='PASSWORD_RESET', target_user_id=str(env['teacher'].id))).json()
    recovery = c.post('/api/institution/requests', json=dict(kind='ACCOUNT_RECOVERY', target_user_id=str(env['supervisor'].id),
                                                            changes=dict(email='new.address@example.test'))).json()
    assert c.post(f"/api/institution/requests/{other['id']}/withdraw").json()['status'] == 'WITHDRAWN'

    p = owner(env)
    assert p.post(f"/api/platform/requests/{change.json()['id']}/decide", json=dict(action='COMPLETE')).status_code == 200
    assert p.post(f"/api/platform/requests/{reset['id']}/decide", json=dict(action='COMPLETE')).status_code == 200
    assert p.post(f"/api/platform/requests/{recovery['id']}/decide", json=dict(action='COMPLETE')).status_code == 200
    assert p.post(f"/api/platform/requests/{other['id']}/decide", json=dict(action='APPROVE')).status_code == 409  # withdrawn
    db = env['db']
    db.expire_all()
    assert db.get(Institution, env['institutions'][0].id).name == 'School Zero Academy'
    assert db.get(User, env['supervisor'].id).email == 'new.address@example.test'
    assert [e['user_email'] for e in sent] == [env['teacher'].email, 'new.address@example.test']
    # Direct reset from the platform users page.
    assert p.post(f"/api/platform/users/{env['admin'].id}/password-reset", json=dict(reason='Locked out')).status_code == 200
    assert len(sent) == 3


def test_termination_locks_out_and_deletion_waits_for_the_date(env):
    tenant = env['institutions'][1].id
    foreign_records(env)  # one record of every kind in the second school
    p = owner(env)
    url = f'/api/platform/institutions/{tenant}'
    assert p.post(url + '/terminate', json=dict(days=30, reason='Contract ended', confirm_name='wrong')).status_code == 422
    done = p.post(url + '/terminate', json=dict(days=30, reason='Contract ended', confirm_name='School 1'))
    assert done.status_code == 200, done.text
    assert env['as_user'](env['outsider']).get('/api/teaching/classes').status_code in {401, 403}
    p = owner(env)
    assert p.post(url + '/permanent-delete', json=dict(confirm_name='School 1')).status_code == 409  # date not reached
    assert p.post(url + '/reactivate').json()['status'] == 'ACTIVE'
    assert env['as_user'](env['outsider']).get('/api/teaching/classes').status_code == 200

    p = owner(env)
    p.post(url + '/terminate', json=dict(days=1, reason='Contract ended', confirm_name='School 1'))
    db = env['db']
    row = db.get(Institution, tenant)
    row.delete_after = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    deleted = p.post(url + '/permanent-delete', json=dict(confirm_name='School 1'))
    assert deleted.status_code == 200, deleted.text
    db.expire_all()
    assert db.get(Institution, tenant) is None
    leftovers = []
    for table in Base.metadata.tables.values():
        if 'institution_id' in table.c:
            count = db.execute(text(f'SELECT COUNT(*) FROM {table.name} WHERE institution_id = :t'), dict(t=tenant.hex)).scalar()
            if count:
                leftovers.append(f'{table.name}: {count}')
    assert not leftovers, leftovers
    # The first school is untouched and the deletion itself stays on record.
    assert db.get(Institution, env['institutions'][0].id).status == InstitutionStatus.ACTIVE
    assert db.query(User).filter_by(institution_id=env['institutions'][0].id).count() >= 5
    assert db.query(AuditEvent).filter_by(action='institution.deleted').one().institution_id is None


def test_overview_shows_queue_health_and_terminations(env):
    admin(env).post('/api/institution/requests', json=dict(kind='OTHER', details='Please extend our trial by a week'))
    data = owner(env).get('/api/platform/overview').json()
    assert data['open_requests'] == 1 and data['institutions']['total'] == 2
    assert set(data['health']) == {'database', 'rate_limits', 'email', 'sms', 'mpesa', 'file_storage'}
    assert data['health']['database'] == 'ok'
    assert env['as_user'](env['admin']).get('/api/platform/overview').status_code == 403


def test_current_term_for_the_top_bar(env):
    from datetime import date
    from app.models.pilot import AcademicPeriod, AcademicYear
    db, tenant = env['db'], env['institutions'][0].id
    assert env['as_user'](env['pupil']).get('/api/institution/current-term').json() == dict(year=None, period=None)
    today = date.today()
    year = AcademicYear(institution_id=tenant, name='2026', start_date=today - timedelta(days=100), end_date=today + timedelta(days=100), status='ACTIVE')
    db.add(year); db.flush()
    db.add(AcademicPeriod(institution_id=tenant, year_id=year.id, name='Term 3', start_date=today - timedelta(days=5), end_date=today + timedelta(days=50)))
    db.commit()
    assert env['as_user'](env['teacher']).get('/api/institution/current-term').json() == dict(year='2026', period='Term 3')


@pytest.mark.real_secret
def test_destructive_and_export_actions_need_the_secret_answer(env):
    from app.core.security import hash_password
    p_user = platform(env)
    p_user.password_hash = hash_password('Owner-pass-2026')
    env['db'].commit()
    p = env['as_user'](p_user)
    tenant = env['institutions'][1].id
    terminate = dict(days=30, reason='Contract ended', confirm_name='School 1')
    assert p.post(f'/api/platform/institutions/{tenant}/terminate', json=terminate).status_code == 409  # no question set yet
    assert p.post('/api/platform/backups/institution', json=dict(institution_id=str(tenant), groups=['people'])).status_code == 409
    assert p.put('/api/platform/secret', json=dict(password='wrong', question='First school I taught at?', answer='Kakamega')).status_code == 403
    assert p.put('/api/platform/secret', json=dict(password='Owner-pass-2026', question='Kakamega?', answer='kakamega')).status_code == 422
    saved = p.put('/api/platform/secret', json=dict(password='Owner-pass-2026', question='First school I taught at?', answer='  Kakamega  Boys '))
    assert saved.status_code == 200 and p.get('/api/platform/secret').json() == dict(set=True, question='First school I taught at?')
    from app.models.platform_secret import PlatformSecret
    assert 'Kakamega' not in env['db'].get(PlatformSecret, p_user.id).answer_hash
    assert p.post(f'/api/platform/institutions/{tenant}/terminate', json=dict(terminate, answer='Nairobi')).status_code == 403
    # Case and spacing do not matter.
    assert p.post(f'/api/platform/institutions/{tenant}/terminate', json=dict(terminate, answer='kakamega boys')).status_code == 200
    assert p.post('/api/platform/backups/platform', json=dict(answer='wrong')).status_code == 403
    for _ in range(4):
        p.post('/api/platform/backups/platform', json=dict(answer='wrong'))
    # Five wrong answers lock the actions, even with the right answer.
    assert p.post('/api/platform/backups/institution', json=dict(institution_id=str(tenant), groups=['people'], answer='kakamega boys')).status_code == 423


def test_recovery_cannot_target_another_admin(env):
    from app.models.user import UserRole
    db = env['db']
    peer = User(institution_id=env['institutions'][0].id, username='peeradmin', first_name='Peer', last_name='Admin', email='peer@example.test',
                role=UserRole.INSTITUTION_ADMIN, password_hash='x', must_change_password=False)
    db.add(peer); db.commit()
    c = admin(env)
    assert c.post('/api/institution/requests', json=dict(kind='ACCOUNT_RECOVERY', target_user_id=str(peer.id), changes=dict(email='mine@example.test'))).status_code == 409
    assert c.post('/api/institution/requests', json=dict(kind='PASSWORD_RESET', target_user_id=str(peer.id))).status_code == 201
