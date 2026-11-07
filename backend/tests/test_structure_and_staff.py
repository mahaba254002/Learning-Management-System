"""Levels, scales, strands, faculties, staff accounts, staff permissions, lifecycle and co-teaching."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from test_teaching import env
from app.core import rate_limit as limiter
from app.core.security import hash_password
from app.models.academic import AcademicClass, Coursework, Subject
from app.models.curriculum import CatalogueUnit
from app.models.institution import Institution
from app.models.invitation import Invitation, InvitationRole, InvitationStatus
from app.models.management import StaffMember
from app.models.pilot import AuthSession
from app.models.structure import AssessmentScale, InstitutionLevel, OfferingTeacher, PasswordSetupToken
from app.models.user import User, UserRole, UserStatus
from app.services import email_service

PASSWORD = 'Secure-Pass-2026!'


@pytest.fixture(autouse=True)
def limits(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, 'incr', lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, 'expire', lambda *args: True)


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(email_service, 'send_email', lambda **message: sent.append(message))
    return sent


def platform(env):
    owner = env['user']('owner', UserRole.PLATFORM_ADMIN)
    owner.institution_id = None
    env['db'].commit()
    return env['as_user'](owner)


def tenant(env):
    return env['cls'].institution_id


def token_from(link):
    return link.split('#token=')[1]


# --- Levels and scales --------------------------------------------------------

def test_platform_assigns_levels_and_scales_institution_reads_them(env):
    client = platform(env)
    root = f"/api/platform/institutions/{tenant(env)}"
    scales = client.get(f'/api/platform/assessment-scales?institution_id={tenant(env)}').json()
    codes = {s['code'] for s in scales}
    assert {'CBE_4', 'CBE_8', 'LETTER_A_E', 'GPA_4', 'GPA_5', 'TVET_COMPETENCE', 'PERCENT'} <= codes
    cbe = next(s for s in scales if s['code'] == 'CBE_4')
    assert [lv['code'] for lv in cbe['levels']] == ['EE', 'ME', 'AE', 'BE'] and float(cbe['levels'][1]['max_percent']) == 79.99
    current = client.get(f'{root}/levels').json()
    body = dict(expected_updated_at=current['updated_at'], levels=[
        dict(level='JUNIOR_SCHOOL', scale_id=cbe['id']), dict(level='SENIOR_SCHOOL', terminology=dict(class_label='Form'))])
    saved = client.put(f'{root}/levels', json=body)
    assert saved.status_code == 200, saved.text
    assert client.put(f'{root}/levels', json=body).status_code == 409  # stale version
    levels = env['as_user'](env['teacher']).get('/api/institution/levels').json()
    assert {lv['level'] for lv in levels} == {'JUNIOR_SCHOOL', 'SENIOR_SCHOOL'}
    junior = next(lv for lv in levels if lv['level'] == 'JUNIOR_SCHOOL')
    assert junior['scale']['code'] == 'CBE_4'
    # Another institution's custom scale cannot be assigned here.
    client = env['as_user'](env['db'].query(User).filter_by(username='owner').one())  # the test client is shared
    foreign = AssessmentScale(institution_id=env['other_cls'].institution_id, name='Private', kind='PERCENT')
    env['db'].add(foreign); env['db'].commit()
    body = dict(expected_updated_at=saved.json()['updated_at'], levels=[dict(level='JUNIOR_SCHOOL', scale_id=str(foreign.id))])
    assert client.put(f'{root}/levels', json=body).status_code == 404
    assert env['as_user'](env['admin']).put(f'{root}/levels', json=body).status_code == 403


def test_custom_scales_validate_and_lock_once_marks_use_them(env):
    client = platform(env)
    root = f"/api/platform/institutions/{tenant(env)}/assessment-scales"
    bad = dict(name='Bad', kind='LETTER', levels=[dict(code='A', label='A', min_percent=50), dict(code='B', label='B', min_percent=10)])
    assert client.post(root, json=bad).status_code == 422  # no zero band
    assert client.post(root, json=dict(name='GPA', kind='GPA', levels=[dict(code='A', label='A', min_percent=50), dict(code='B', label='B', min_percent=0)])).status_code == 422
    good = dict(name='School letters', kind='LETTER', levels=[dict(code='a', label='Top', min_percent=60), dict(code='b', label='Pass', min_percent=0)])
    created = client.post(root, json=good)
    assert created.status_code == 201, created.text
    scale = created.json()
    assert [lv['code'] for lv in scale['levels']] == ['A', 'B'] and not scale['preset']
    edited = client.put(f"{root}/{scale['id']}", json={**good, 'name': 'Renamed', 'expected_updated_at': scale['updated_at']})
    assert edited.status_code == 200, edited.text
    env['work'].scale_id = uuid.UUID(scale['id']); env['db'].commit()
    again = client.put(f"{root}/{scale['id']}", json={**good, 'expected_updated_at': edited.json()['updated_at']})
    assert again.status_code == 409
    # Presets are never edited in place.
    preset = next(s for s in client.get('/api/platform/assessment-scales').json() if s['code'] == 'CBE_4')
    assert client.put(f"{root}/{preset['id']}", json={**good, 'expected_updated_at': preset['updated_at']}).status_code == 404


def assign_level(env, level='JUNIOR_SCHOOL', code='LETTER_A_E'):
    client = platform(env)
    root = f"/api/platform/institutions/{tenant(env)}"
    scale = next(s for s in client.get('/api/platform/assessment-scales').json() if s['code'] == code)
    current = client.get(f'{root}/levels').json()
    saved = client.put(f'{root}/levels', json=dict(expected_updated_at=current['updated_at'], levels=[dict(level=level, scale_id=scale['id'])])).json()
    return saved['levels'][0]['id'], scale


def test_class_level_scale_is_copied_into_new_assessments(env):
    level_id, scale = assign_level(env)
    client = env['as_user'](env['admin'])
    group = client.put(f"/api/teaching/classes/{env['cls'].id}", json=dict(name='Form 1', academic_year='2026', stream='East',
                       supervisor_id=str(env['supervisor'].id), education_level_id=level_id))
    assert group.status_code == 200, group.text
    assert group.json()['stream'] == 'East'
    client = env['as_user'](env['teacher'])
    work = client.post(f"/api/teaching/subjects/{env['subject'].id}/coursework", json=dict(title='Test', instructions='Do it', max_score=50, published=True))
    assert work.status_code == 201, work.text
    saved = client.put(f"/api/teaching/coursework/{work.json()['id']}/scores", json=dict(entries=[dict(student_id=str(env['student'].id), score=40)]))
    assert saved.status_code == 200, saved.text
    row = env['db'].get(Coursework, uuid.UUID(work.json()['id']))
    env['db'].refresh(row)
    assert row.scale_id == uuid.UUID(scale['id'])
    assert [b['label'] for b in row.grading_bands] == ['A', 'B', 'C', 'D', 'E']


def test_competency_scale_sets_rubric_labels(env):
    level_id, _ = assign_level(env, code='CBE_4')
    institution = env['db'].get(Institution, tenant(env))
    institution.academic_configuration = dict(assessment_policy='MIXED'); env['db'].commit()
    env['as_user'](env['admin']).put(f"/api/teaching/classes/{env['cls'].id}", json=dict(name='Form 1', academic_year='2026', supervisor_id=str(env['supervisor'].id), education_level_id=level_id))
    work = env['as_user'](env['teacher']).post(f"/api/teaching/subjects/{env['subject'].id}/coursework",
        json=dict(title='Observation', instructions='Observe', max_score=4, assessment_mode='COMPETENCY'))
    assert work.status_code == 201, work.text
    assert work.json()['rubric_labels'] == ['Exceeding expectations', 'Meeting expectations', 'Approaching expectations', 'Below expectations']


def test_inactive_or_foreign_levels_cannot_be_used(env):
    client = env['as_user'](env['admin'])
    other = InstitutionLevel(institution_id=env['other_cls'].institution_id, level='TVET')
    env['db'].add(other); env['db'].commit()
    body = dict(name='New', academic_year='2026', education_level_id=str(other.id))
    assert client.post('/api/teaching/classes', json=body).status_code == 404
    own = InstitutionLevel(institution_id=tenant(env), level='ECDE', active=False)
    env['db'].add(own); env['db'].commit()
    assert client.post('/api/teaching/classes', json={**body, 'education_level_id': str(own.id)}).status_code == 422


# --- Strands and faculties --------------------------------------------------

def test_strands_two_levels_and_assessments_point_at_own_learning_area(env):
    db = env['db']
    area, other_area = CatalogueUnit(institution_id=tenant(env), code='MATH', name='Mathematics'), CatalogueUnit(institution_id=tenant(env), code='ENG', name='English')
    db.add_all([area, other_area]); db.flush()
    env['subject'].catalogue_id = area.id; db.commit()
    client = env['as_user'](env['admin'])
    root = f'/api/institution/academic-structure/catalogue/{area.id}/strands'
    strand = client.post(root, json=dict(code='num', name='Numbers'))
    assert strand.status_code == 201, strand.text
    sub = client.post(root, json=dict(code='num.1', name='Whole numbers', parent_id=strand.json()['id']))
    assert sub.status_code == 201
    assert client.post(root, json=dict(code='num.1.1', name='Too deep', parent_id=sub.json()['id'])).status_code == 422
    elsewhere = client.post(f'/api/institution/academic-structure/catalogue/{other_area.id}/strands', json=dict(code='read', name='Reading'))
    assert client.post(root, json=dict(code='x', name='Wrong parent', parent_id=elsewhere.json()['id'])).status_code == 422
    teacher = env['as_user'](env['teacher'])
    assert [s['code'] for s in teacher.get(f"/api/teaching/subjects/{env['subject'].id}/strands").json()] == ['NUM', 'NUM.1']
    work = dict(title='Strand test', instructions='Do it', max_score=10)
    assert teacher.post(f"/api/teaching/subjects/{env['subject'].id}/coursework", json={**work, 'strand_id': elsewhere.json()['id']}).status_code == 422
    assert teacher.post(f"/api/teaching/subjects/{env['subject'].id}/coursework", json={**work, 'strand_id': sub.json()['id']}).status_code == 201
    assert env['as_user'](env['outsider']).get(f"/api/teaching/subjects/{env['subject'].id}/strands").status_code == 404


def test_faculties_hold_departments_only_one_level_deep(env):
    client = env['as_user'](env['admin'])
    faculty = client.post('/api/management/departments', json=dict(code='FSC', name='Faculty of Science', kind='FACULTY')).json()
    dept = client.post('/api/management/departments', json=dict(code='CHEM', name='Chemistry', parent_id=faculty['id']))
    assert dept.status_code == 201, dept.text
    assert client.post('/api/management/departments', json=dict(code='BIO', name='Bio', parent_id=dept.json()['id'])).status_code == 422
    assert client.post('/api/management/departments', json=dict(code='F2', name='F2', kind='FACULTY', parent_id=faculty['id'])).status_code == 422
    body = dict(code='FSC', name='Faculty of Science', kind='DEPARTMENT', expected_updated_at=faculty['updated_at'])
    assert client.put(f"/api/management/departments/{faculty['id']}", json=body).status_code == 409


# --- Staff accounts, set-password links and the staff role -----------------

def new_staff(client, **values):
    body = dict(staff_number='B-1', first_name='Grace', last_name='Wanjiru', category='NON_TEACHING', job_title='Bursar',
                email='grace@example.test', **values)
    return client.post('/api/management/staff', json=body)


def test_direct_staff_creation_sends_single_use_setup_link(env, outbox):
    client = env['as_user'](env['admin'])
    created = new_staff(client, login='LINK')
    assert created.status_code == 201, created.text
    data = created.json()
    assert data['account']['role'] == 'STAFF' and data['credentials']['emailed'] is True
    assert data['credentials']['setup_link'] is None and data['credentials']['temporary_password'] is None
    link = outbox[0]['html_body'].split('href="')[1].split('"')[0]
    token = token_from(link)
    assert env['db'].query(PasswordSetupToken).one().token_digest != token  # only a digest is stored
    public = env['client']
    public.cookies.clear()
    check = public.post('/api/auth/set-password/check', json=dict(token=token))
    assert check.status_code == 200 and check.json()['login_path'] == '/teacher/login'
    assert public.post('/api/auth/set-password', json=dict(token=token, new_password='short', confirm_password='short')).status_code == 400
    done = public.post('/api/auth/set-password', json=dict(token=token, new_password=PASSWORD, confirm_password=PASSWORD))
    assert done.status_code == 200, done.text
    assert public.post('/api/auth/set-password', json=dict(token=token, new_password=PASSWORD, confirm_password=PASSWORD)).status_code == 400
    login = public.post('/api/auth/teacher/login', json=dict(email='grace@example.test', password=PASSWORD))
    assert login.status_code == 200 and login.json()['user']['role'] == 'STAFF'
    assert public.post('/api/auth/login', json=dict(email='grace@example.test', password=PASSWORD)).status_code == 401


def test_setup_link_shown_when_email_fails_and_expires(env):
    client = env['as_user'](env['admin'])
    data = new_staff(client, login='LINK').json()
    link = data['credentials']['setup_link']
    assert link and data['credentials']['emailed'] is False
    row = env['db'].query(PasswordSetupToken).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1); env['db'].commit()
    assert env['client'].post('/api/auth/set-password/check', json=dict(token=token_from(link))).status_code == 400
    # A fresh link retires the old one.
    again = client.post(f"/api/management/staff/{data['id']}/account", json=dict(delivery='LINK'))
    assert again.status_code == 200 and again.json()['setup_link']
    assert env['db'].query(PasswordSetupToken).filter(PasswordSetupToken.used_at.is_(None)).count() == 1


def test_temporary_password_expires(env):
    client = env['as_user'](env['admin'])
    data = new_staff(client, login='TEMPORARY_PASSWORD').json()
    password = data['credentials']['temporary_password']
    public = env['client']; public.cookies.clear()
    assert public.post('/api/auth/teacher/login', json=dict(email='grace@example.test', password=password)).status_code == 200
    user = env['db'].get(User, uuid.UUID(data['account']['id']))
    user.temporary_password_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1); env['db'].commit()
    assert public.post('/api/auth/teacher/login', json=dict(email='grace@example.test', password=password)).status_code == 403


def test_credentials_are_never_created_from_a_delegated_workspace(env):
    owner = platform(env)
    start = owner.post('/api/workspace-access/start', json=dict(reason='Support request in tests', target_user_id=str(env['admin'].id)))
    headers = {'X-Workspace-Token': start.json()['token']}
    body = dict(staff_number='B-1', first_name='G', last_name='W', category='NON_TEACHING', job_title='Bursar', email='g@example.test')
    # Platform delegation is read-only, so this stops even earlier.
    assert owner.post('/api/management/staff', json={**body, 'login': 'LINK'}, headers=headers).status_code == 403
    assert env['db'].query(User).filter_by(email='g@example.test').count() == 0


def test_staff_permissions_grant_only_what_is_ticked(env):
    client = env['as_user'](env['admin'])
    data = new_staff(client, login='TEMPORARY_PASSWORD').json()
    user = env['db'].get(User, uuid.UUID(data['account']['id']))
    user.must_change_password = False; env['db'].commit()
    staff = env['as_user'](user)
    assert staff.get('/api/management/staff').status_code == 403
    assert staff.get('/api/staff/me').json()['permissions'] == []
    client = env['as_user'](env['admin'])
    saved = client.put(f"/api/management/staff/{data['id']}/permissions", json=dict(permissions=['staff.view', 'students.view']))
    assert saved.status_code == 200, saved.text
    assert client.put(f"/api/management/staff/{data['id']}/permissions", json=dict(permissions=['payroll.manage'])).status_code == 422
    staff = env['as_user'](user)
    assert staff.get('/api/management/staff').status_code == 200
    assert staff.get('/api/management/students').json()['items'][0]['admission_number'] == 'A001'
    assert staff.get(f"/api/management/attendance?day={datetime.now().date()}").status_code == 403
    assert staff.post('/api/management/staff', json=dict(staff_number='X', first_name='X', last_name='X', category='NON_TEACHING', job_title='X')).status_code == 403
    assert staff.get('/api/teaching/classes').status_code == 403
    # Permissions stop when the staff record is no longer active.
    env['db'].query(StaffMember).filter_by(user_id=user.id).one().status = 'ON_LEAVE'; env['db'].commit()
    assert staff.get('/api/management/staff').status_code == 403
    # Teachers cannot be given staff permissions.
    teacher_record = env['db'].query(StaffMember).filter_by(user_id=env['teacher'].id).one()
    assert env['as_user'](env['admin']).get(f'/api/management/staff/{teacher_record.id}/permissions').status_code == 409


def test_staff_account_role_must_match_category(env):
    client = env['as_user'](env['admin'])
    body = dict(staff_number='S-9', first_name='Sam', last_name='K', category='NON_TEACHING', job_title='Clerk', user_id=str(env['unrelated'].id))
    assert client.post('/api/management/staff', json=body).status_code == 422


# --- Lifecycle ------------------------------------------------------------

def test_account_lifecycle_steps_reasons_and_handover(env):
    client = env['as_user'](env['admin'])
    url = f"/api/institution/users/{env['teacher'].id}/status"
    assert client.put(url, json=dict(status='ARCHIVED', reason='Left')).status_code == 409  # one step at a time
    assert client.put(url, json=dict(status='DEACTIVATED')).status_code == 422  # reason required
    assert client.put(url, json=dict(status='DEACTIVATED', reason='Left the school')).status_code == 409  # still leads Math
    assert client.put(url, json=dict(status='SUSPENDED')).status_code == 200
    env['db'].add(AuthSession(id=uuid.uuid4(), user_id=env['unrelated'].id, refresh_digest='x', expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
    env['db'].commit()
    unrelated = f"/api/institution/users/{env['unrelated'].id}/status"
    assert client.put(unrelated, json=dict(status='DEACTIVATED', reason='Contract ended')).status_code == 200
    assert env['db'].query(AuthSession).filter_by(user_id=env['unrelated'].id).one().revoked
    assert env['db'].query(StaffMember).filter_by(user_id=env['unrelated'].id).one().status == 'INACTIVE'
    assert client.put(unrelated, json=dict(status='ARCHIVED', reason='Records kept')).status_code == 200
    listed = client.get('/api/institution/users').json()
    assert str(env['unrelated'].id) not in {u['id'] for u in listed['items']}
    assert str(env['unrelated'].id) in {u['id'] for u in client.get('/api/institution/users?include_archived=true').json()['items']}
    assert client.get('/api/management/staff?search=T-unrelated').json()['total'] == 0
    assert client.put(unrelated, json=dict(status='DEACTIVATED', reason='Unarchive')).status_code == 200
    assert client.put(unrelated, json=dict(status='ACTIVE')).status_code == 200
    assert env['db'].query(StaffMember).filter_by(user_id=env['unrelated'].id).one().status == 'ACTIVE'
    assert client.put(f"/api/institution/users/{env['admin'].id}/status", json=dict(status='SUSPENDED')).status_code == 403


# --- Co-teaching through offerings ----------------------------------------

def test_changing_offering_teacher_keeps_one_lead_and_revokes_old_lead(env):
    client = env['as_user'](env['admin'])
    url = f"/api/teaching/subjects/{env['subject'].id}"
    body = dict(name='Math', teacher_id=str(env['teacher'].id))
    assert client.put(url, json=body).status_code == 200
    assert {r.user_id: r.role for r in env['db'].query(OfferingTeacher)} == {env['teacher'].id: 'LEAD'}
    assert client.put(url, json={**body, 'teacher_id': str(env['unrelated'].id)}).status_code == 200
    assert {r.user_id: r.role for r in env['db'].query(OfferingTeacher)} == {env['unrelated'].id: 'LEAD'}
    assert env['as_user'](env['teacher']).get(f"{url}/periods").status_code == 404
    client = env['as_user'](env['admin'])
    created = client.post(f"/api/teaching/classes/{env['cls'].id}/subjects", json=dict(name='Physics', teacher_id=str(env['teacher'].id)))
    assert created.status_code == 201
    assert env['db'].query(OfferingTeacher).filter_by(subject_id=uuid.UUID(created.json()['id'])).one().role == 'LEAD'


def test_admin_can_open_a_staff_workspace(env):
    client = env['as_user'](env['admin'])
    data = new_staff(client, login='TEMPORARY_PASSWORD').json()
    user = env['db'].get(User, uuid.UUID(data['account']['id']))
    user.must_change_password = False; env['db'].commit()
    start = env['as_user'](env['admin']).post('/api/workspace-access/start', json=dict(target_user_id=str(user.id)))
    assert start.status_code == 200, start.text


# --- Invitations now produce staff records ---------------------------------

def test_approved_invitation_creates_staff_record_and_setup_link(env, outbox):
    invitation = Invitation(institution_id=tenant(env), invited_role=InvitationRole.TEACHER, email='newteacher@example.test',
                            invite_token=uuid.uuid4().hex, invited_by=env['admin'].id, status=InvitationStatus.SUBMITTED,
                            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
                            submitted_data=dict(first_name='New', last_name='Teacher', gender='FEMALE', date_of_birth='1991-02-03',
                                                qualification='BEd', employment_type='VISITING', phone=None, specialization=None))
    env['db'].add(invitation); env['db'].commit()
    result = env['as_user'](env['admin']).post(f'/api/institution/invitations/{invitation.id}/approve')
    assert result.status_code == 200, result.text
    assert result.json()['credentials_emailed'] is True and 'temporary_password' not in result.json()
    assert 'set-password#token=' in outbox[0]['html_body'] and 'password:' not in outbox[0]['html_body'].lower()
    profile = env['db'].query(StaffMember).filter_by(email='newteacher@example.test').one()
    assert profile.category == 'TEACHING' and profile.employment_type == 'CONTRACT' and profile.invitation_id == invitation.id
    teachers = env['as_user'](env['admin']).get('/api/institution/teachers').json()
    assert any(t['email'] == 'newteacher@example.test' and t['staff_number'].startswith('T') for t in teachers)


# Routes any signed-in staff account may read, whatever its permissions.
STAFF_READABLE = {
    '/api/me', '/api/staff/me', '/api/institution/modules', '/api/institution/academic-configuration',
    '/api/institution/learning-settings', '/api/institution/subscription', '/api/institution/levels', '/api/announcements',
    # Personal inbox: every signed-in person has one.
    '/api/notifications',
}


def test_staff_without_permissions_reads_nothing_else(env):
    import re
    from app.main import app
    client = env['as_user'](env['admin'])
    data = new_staff(client, login='TEMPORARY_PASSWORD').json()
    user = env['db'].get(User, uuid.UUID(data['account']['id']))
    user.must_change_password = False; env['db'].commit()
    ids = dict(class_id=env['cls'].id, subject_id=env['subject'].id, coursework_id=env['work'].id, work_id=env['work'].id,
               student_id=env['student'].id, user_id=env['pupil'].id, teacher_id=uuid.uuid4(), staff_id=uuid.UUID(data['id']),
               institution_id=tenant(env), document_id=uuid.uuid4(), course_id=uuid.uuid4(), department_id=uuid.uuid4(),
               record_id=uuid.uuid4(), allocation_id=uuid.uuid4(), year_id=uuid.uuid4(), material_id=uuid.uuid4(),
               invitation_id=uuid.uuid4(), strand_id=uuid.uuid4(), scale_id=uuid.uuid4(), kind='departments', token='x' * 40, prompt_id=uuid.uuid4(), sequence=1, transaction_id=uuid.uuid4(),
               guardian_id=uuid.uuid4(), discipline_id=uuid.uuid4(), announcement_id=uuid.uuid4(),
               period_id=uuid.uuid4(), slot_id=uuid.uuid4(), entry_id=uuid.uuid4(), unavailability_id=uuid.uuid4(), change_id=uuid.uuid4(), request_id=uuid.uuid4(), message_id=uuid.uuid4(),
               file_id=uuid.uuid4(), attempt_id=uuid.uuid4(), window_id=uuid.uuid4())
    staff = env['as_user'](user)
    leaks = []
    for route in app.routes:
        path = getattr(route, 'path', '')
        if 'GET' not in getattr(route, 'methods', set()) or not path.startswith('/api/') or path.startswith('/api/invitations/') or path.startswith('/api/drafts/'):
            continue
        url = re.sub(r'{(\w+)}', lambda m: str(ids[m.group(1)]), path)
        query = '?day=2026-01-01' if path.endswith('attendance') else ''
        response = staff.get(url + query)
        if response.status_code < 300 and path not in STAFF_READABLE:
            leaks.append(f'{path} -> {response.status_code}')
    assert not leaks, leaks
    assert staff.get('/api/academic-documents').status_code == 403
    assert staff.get('/api/dashboard').status_code == 403
