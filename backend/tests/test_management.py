"""Management-only institutions, module boundaries and employee record integrity."""
import uuid
from datetime import timedelta
import pytest
from sqlalchemy.exc import IntegrityError
from test_teaching import env
from app.core import rate_limit as limiter
from app.core.security import hash_password
from app.models.institution import Institution, InstitutionStatus
from app.models.management import StaffMember, StaffAttendance
from app.models.structure import OfferingTeacher
from app.models.curriculum import CatalogueUnit, Department
from app.models.user import UserRole, User
from app.models.academic import Student, Coursework
from app.services.modules import module_presets
from app.services.subscriptions import kenya_today
from app.services import backups


@pytest.fixture(autouse=True)
def limits(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, 'incr', lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, 'expire', lambda *args: True)


def configure(env, preset='MANAGEMENT'):
    institution = env['db'].get(Institution, env['cls'].institution_id)
    institution.module_settings = module_presets()[preset]
    env['db'].commit()
    return institution


def platform(env):
    owner = env['user']('owner', UserRole.PLATFORM_ADMIN)
    owner.institution_id = None
    env['db'].commit()
    return owner


def employee(env, number='ST-001', category='TEACHING', **values):
    client = env['as_user'](env['admin'])
    body = dict(staff_number=number, first_name='Amina', last_name='Otieno', category=category, job_title='Lecturer', **values)
    response = client.post('/api/management/staff', json=body)
    assert response.status_code == 201, response.text
    return response.json()


def edit_body(record, **changes):
    fields = ['staff_number', 'first_name', 'last_name', 'category', 'job_title', 'department_id', 'user_id', 'email', 'phone', 'employment_type', 'status', 'joined_on']
    return {**{key: record[key] for key in fields}, 'expected_updated_at': record['updated_at'], **changes}


def test_presets_defaults_configuration_permissions_and_conflict(env):
    client = env['as_user'](env['admin'])
    assert all(client.get('/api/institution/modules').json()['modules'].values())
    owner = platform(env)
    root = f"/api/platform/institutions/{env['cls'].institution_id}/modules"
    assert env['as_user'](env['admin']).get(root).status_code == 403
    client = env['as_user'](owner)
    initial = client.get(root).json()
    body = dict(modules=module_presets()['MANAGEMENT'], expected_updated_at=initial['updated_at'])
    result = client.put(root, json=body)
    assert result.status_code == 200, result.text
    assert not result.json()['modules']['student_portal']
    assert client.put(root, json=body).status_code == 409
    invalid = {**result.json()['modules'], 'student_portal': True}
    assert client.put(root, json=dict(modules=invalid, expected_updated_at=result.json()['updated_at'])).status_code == 422
    institution = env['db'].get(Institution, env['cls'].institution_id)
    institution.status = InstitutionStatus.ARCHIVED; env['db'].commit()
    assert client.put(root, json=dict(modules=module_presets()['FULL'], expected_updated_at=institution.updated_at.isoformat())).status_code == 409


@pytest.mark.parametrize('suffix', [
    '/api/teaching/classes/{class_id}/students', '/api/teaching/classes/{class_id}/attendance',
    '/api/teaching/subjects/{subject_id}/coursework', '/api/teaching/subjects/{subject_id}/materials',
    '/api/teaching/coursework/{work_id}/scores', '/api/teaching/coursework/{work_id}/submissions',
    '/api/teaching/subjects/{subject_id}/final-grades', '/api/teaching/classes/{class_id}/report',
    '/api/academic-documents', '/api/institution/progression/history',
])
def test_management_only_rejects_disabled_endpoints(env, suffix):
    configure(env)
    path = suffix.format(class_id=env['cls'].id, subject_id=env['subject'].id, work_id=env['work'].id)
    assert env['as_user'](env['admin']).get(path).status_code == 403
    assert env['db'].query(Coursework).count() == 2


def test_modules_apply_to_delegated_workspaces_and_existing_student_sessions(env):
    configure(env)
    owner = platform(env)
    client = env['as_user'](owner)
    workspace = client.post('/api/workspace-access/start', json=dict(reason='Support request in tests', target_user_id=str(env['admin'].id)))
    assert workspace.status_code == 200, workspace.text
    token = workspace.json()['token']
    assert client.get(f"/api/teaching/classes/{env['cls'].id}/students", headers={'X-Workspace-Token': token}).status_code == 403
    client = env['as_user'](env['pupil'])
    assert client.get('/api/student/profile').status_code == 403
    assert client.get('/api/dashboard').status_code == 403
    assert client.get('/api/me').status_code == 200
    assert client.post('/api/auth/logout').status_code == 200


def test_delegation_can_be_exited_after_target_portal_or_account_disabled(env):
    owner = platform(env)
    client = env['as_user'](owner)
    started = client.post('/api/workspace-access/start', json=dict(reason='Support request in tests', target_user_id=str(env['pupil'].id)))
    assert started.status_code == 200
    configure(env)
    env['pupil'].login_enabled = False; env['db'].commit()
    response = client.post('/api/workspace-access/stop', headers={'X-Workspace-Token': started.json()['token']})
    assert response.status_code == 200 and response.json()['id'] == str(owner.id)


def test_student_cannot_login_or_refresh_when_portal_disabled(env):
    pupil = env['pupil']; pupil.password_hash = hash_password('Secure-Pass-2026!'); env['db'].commit()
    client = env['as_user'](pupil)
    assert client.post('/api/auth/student/login', json=dict(email=pupil.email, password='Secure-Pass-2026!')).status_code == 200
    configure(env)
    assert client.post('/api/auth/refresh').status_code == 403
    assert client.post('/api/auth/student/login', json=dict(email=pupil.email, password='Secure-Pass-2026!')).status_code == 403


def test_management_directory_departments_without_accounts_and_pagination(env):
    configure(env)
    client = env['as_user'](env['admin'])
    department = client.post('/api/management/departments', json=dict(code='ops', name='Operations')).json()
    staff = employee(env, category='NON_TEACHING', department_id=department['id'])
    assert staff['teacher_user_id'] is None and staff['email'] is None
    assert env['db'].query(User).count() == 7
    result = client.get('/api/management/staff?category=NON_TEACHING&limit=1').json()
    assert result['total'] == 1 and result['items'][0]['id'] == staff['id']
    assert client.get('/api/management/staff?search=%25').json()['total'] == 0
    assert client.get('/api/management/staff?offset=10').json()['items'] == []
    edited = client.put(f"/api/management/staff/{staff['id']}", json=edit_body(staff, phone='0700000000'))
    assert edited.status_code == 200
    assert client.put(f"/api/management/staff/{staff['id']}", json=edit_body(staff)).status_code == 409
    assert client.post('/api/management/staff', json=edit_body(staff)).status_code == 409
    assert env['as_user'](env['teacher']).get('/api/management/staff').status_code == 403
    assert env['as_user'](env['pupil']).get('/api/management/staff').status_code == 403
    assert env['as_user'](env['outsider']).get('/api/management/staff').status_code == 403


def test_directory_tenant_links_and_database_constraints(env):
    configure(env)
    foreign = Department(institution_id=env['other_cls'].institution_id, code='X', name='Other')
    env['db'].add(foreign); env['db'].commit()
    client = env['as_user'](env['admin'])
    body = dict(staff_number='S1', first_name='Jane', last_name='Doe', category='TEACHING', job_title='Teacher')
    assert client.post('/api/management/staff', json={**body, 'department_id': str(foreign.id)}).status_code == 404
    assert client.post('/api/management/staff', json={**body, 'user_id': str(env['outsider'].id)}).status_code == 404
    assert client.post('/api/management/staff', json={**body, 'user_id': str(env['pupil'].id)}).status_code == 422
    row = StaffMember(institution_id=env['cls'].institution_id, department_id=foreign.id, **body)
    env['db'].add(row)
    with pytest.raises(IntegrityError): env['db'].commit()
    env['db'].rollback()


def staff_of(env, who):
    return env['db'].query(StaffMember).filter_by(user_id=env[who].id).one()


def test_allocations_are_offering_teachers_with_workload_and_lifecycle(env):
    configure(env)
    client = env['as_user'](env['admin'])
    co = staff_of(env, 'unrelated')
    support = employee(env, number='SUP-1', category='NON_TEACHING')
    subject = str(env['subject'].id)
    body = dict(subject_id=subject, staff_id=str(co.id), weekly_hours='8.5')
    assert client.post('/api/management/allocations', json={**body, 'subject_id': str(env['other_subject'].id)}).status_code == 404
    assert client.post('/api/management/allocations', json={**body, 'staff_id': support['id']}).status_code == 422
    # Before the allocation the second teacher cannot see the class.
    assert env['as_user'](env['unrelated']).get(f"/api/teaching/subjects/{subject}/periods").status_code == 404
    client = env['as_user'](env['admin'])  # The test client is shared; switch back.
    first = client.post('/api/management/allocations', json=body)
    assert first.status_code == 201, first.text
    row = first.json()
    assert row['role'] == 'ASSISTANT'
    assert client.post('/api/management/allocations', json=body).status_code == 409
    assert client.post('/api/management/allocations', json={**body, 'group_name': 'B', 'weekly_hours': '160'}).status_code == 422
    # Co-teachers get the same teaching access as the lead.
    teacher = env['as_user'](env['unrelated'])
    assert teacher.get(f"/api/teaching/subjects/{subject}/periods").status_code == 200
    assert [c['id'] for c in teacher.get('/api/teaching/classes').json()] == [str(env['cls'].id)]
    assert len(teacher.get('/api/teacher/staff-allocations').json()['allocations']) == 1
    client = env['as_user'](env['admin'])
    record = client.get(f'/api/management/staff?search={co.staff_number}').json()['items'][0]
    assert client.put(f"/api/management/staff/{co.id}", json=edit_body(record, status='INACTIVE')).status_code == 409
    # Promote the co-teacher; the previous lead stays on as a co-teacher.
    promoted = client.put(f"/api/management/allocations/{row['id']}", json=dict(role='LEAD', weekly_hours='8.5', expected_updated_at=row['updated_at']))
    assert promoted.status_code == 200, promoted.text
    env['db'].expire_all()
    assert env['db'].get(type(env['subject']), env['subject'].id).teacher_id == env['unrelated'].id
    roles = {r.user_id: r.role for r in env['db'].query(OfferingTeacher).filter_by(subject_id=env['subject'].id)}
    assert roles == {env['unrelated'].id: 'LEAD', env['teacher'].id: 'ASSISTANT'}
    assert client.delete(f"/api/management/allocations/{row['id']}").status_code == 409
    old = env['db'].query(OfferingTeacher).filter_by(subject_id=env['subject'].id, user_id=env['teacher'].id).one()
    assert client.delete(f"/api/management/allocations/{old.id}").status_code == 200
    assert env['as_user'](env['teacher']).get(f"/api/teaching/subjects/{subject}/periods").status_code == 404


def test_staff_attendance_atomicity_conflicts_filters_and_history(env):
    configure(env)
    first = employee(env)
    second = employee(env, number='S2', category='NON_TEACHING')
    client = env['as_user'](env['admin']); today = kenya_today().isoformat()
    entries = [dict(staff_id=first['id'], status='PRESENT'), dict(staff_id=second['id'], status='LEAVE', note='Approved')]
    assert client.put('/api/management/attendance', json=dict(day=today, entries=entries)).status_code == 200
    register = client.get(f'/api/management/attendance?day={today}').json()
    # The three fixture teachers also have staff records, without attendance.
    assert register['total'] == 5
    versions = {row['staff']['id']: row['attendance']['updated_at'] for row in register['items'] if row['attendance']}
    assert set(versions) == {first['id'], second['id']}
    entries[0].update(status='LATE', expected_updated_at=versions[first['id']])
    # Missing the second version must reject the whole batch.
    assert client.put('/api/management/attendance', json=dict(day=today, entries=entries)).status_code == 409
    assert env['db'].query(StaffAttendance).filter_by(staff_id=uuid.UUID(first['id'])).one().status == 'PRESENT'
    entries[1]['expected_updated_at'] = versions[second['id']]
    assert client.put('/api/management/attendance', json=dict(day=today, entries=entries)).status_code == 200
    assert client.put('/api/management/attendance', json=dict(day=today, entries=entries)).status_code == 409
    assert client.put('/api/management/attendance', json=dict(day=today, entries=[entries[0], entries[0]])).status_code == 422
    assert client.put('/api/management/attendance', json=dict(day=(kenya_today()+timedelta(days=1)).isoformat(), entries=[dict(staff_id=first['id'], status='ABSENT')])).status_code == 422
    assert client.put(f"/api/management/staff/{second['id']}", json=edit_body(second, status='INACTIVE')).status_code == 200
    assert client.get(f'/api/management/attendance?day={today}&category=NON_TEACHING').json()['total'] == 1
    overview = client.get('/api/management/overview').json()
    assert overview['active_staff'] == 4 and overview['attendance_today'] == {'LATE': 1, 'LEAVE': 1}


def test_student_records_without_signin_and_explicit_later_activation(env):
    configure(env, 'MANAGEMENT_WITH_STUDENTS')
    client = env['as_user'](env['admin'])
    response = client.post(f"/api/teaching/classes/{env['cls'].id}/students", json=dict(first_name='Record', last_name='Only', admission_number='R-001', login_enabled=False))
    assert response.status_code == 201, response.text
    data = response.json()
    assert data['temporary_password'] is None and data['login_identity'] is None
    assert data['student']['login_enabled'] is False
    root = f"/api/institution/students/{data['student']['user_id']}"
    assert client.post(root + '/reset-password').status_code == 403
    assert client.put(root + '/login', json=dict(email='record@example.test')).status_code == 403
    configure(env, 'FULL')
    user = env['db'].get(User, uuid.UUID(data['student']['user_id']))
    assert not user.login_enabled  # A package upgrade alone never grants account access.
    assert env['as_user'](user).get('/api/me').status_code == 401
    client = env['as_user'](env['admin'])
    assert client.put(root + '/login', json=dict(email='record@example.test', login_enabled=True)).status_code == 200
    assert client.post(root + '/reset-password').status_code == 200


def test_module_and_staff_history_in_backup(env):
    institution = configure(env)
    staff = employee(env)
    client = env['as_user'](env['admin'])
    assert client.put('/api/management/attendance', json=dict(day=kenya_today().isoformat(), entries=[dict(staff_id=staff['id'], status='PRESENT')])).status_code == 200
    raw = backups.export_institution(env['db'], institution.id, ['people', 'academics', 'attendance'])
    manifest, payload = backups.open_archive(raw)
    saved, tables = backups.institution_payload(manifest, payload)
    assert saved['module_settings'] == module_presets()['MANAGEMENT']
    assert len(tables['staff_members']) == 4 and len(tables['staff_attendance']) == 1
    fingerprint = backups.merge_fingerprint(env['db'], institution.id, tables)
    assert backups.merge_institution(env['db'], manifest, payload, fingerprint) == institution.id


def test_student_imports_without_portal_issue_no_credentials_and_recheck_package(env):
    configure(env, 'MANAGEMENT_WITH_STUDENTS')
    client = env['as_user'](env['admin'])
    parsed = client.post('/api/institution/student-imports/parse?filename=records.csv',
        content=b'first_name,last_name,admission_number\nRecord,Student,IMP-1\n', headers={'Content-Type': 'text/csv'})
    assert parsed.status_code == 200, parsed.text
    body = dict(class_id=str(env['cls'].id), rows=parsed.json()['rows'])
    preview = client.post('/api/institution/student-imports/preview', json=body)
    assert preview.status_code == 200 and preview.json()['errors'] == []
    assert preview.json()['students'][0]['login_enabled'] is False
    configure(env, 'FULL')
    assert client.post('/api/institution/student-imports/commit', json={**body, 'preview_token': preview.json()['preview_token']}).status_code == 409
    configure(env, 'MANAGEMENT_WITH_STUDENTS')
    preview = client.post('/api/institution/student-imports/preview', json=body).json()
    result = client.post('/api/institution/student-imports/commit', json={**body, 'preview_token': preview['preview_token']})
    assert result.status_code == 200, result.text
    assert result.json() == dict(created=1, credentials=[])
    user = env['db'].query(User).filter_by(first_name='Record').one()
    assert user.login_enabled is False


def test_another_institution_admin_cannot_access_staff_or_attendance(env):
    configure(env)
    staff = employee(env)
    other_admin = env['user']('otheradmin', UserRole.INSTITUTION_ADMIN, tenant=1)
    env['db'].commit()
    client = env['as_user'](other_admin)
    assert client.get('/api/management/staff').json()['total'] == 1  # their own teacher
    assert client.put(f"/api/management/staff/{staff['id']}", json=edit_body(staff)).status_code == 404
    assert client.put('/api/management/attendance', json=dict(day=kenya_today().isoformat(), entries=[dict(staff_id=staff['id'], status='PRESENT')])).status_code == 404
    assert env['db'].query(StaffAttendance).count() == 0


def test_switching_off_staff_attendance_preserves_register_but_blocks_api(env):
    institution = configure(env)
    staff = employee(env)
    client = env['as_user'](env['admin'])
    body = dict(day=kenya_today().isoformat(), entries=[dict(staff_id=staff['id'], status='PRESENT')])
    assert client.put('/api/management/attendance', json=body).status_code == 200
    institution.module_settings = {**institution.module_settings, 'staff_attendance': False}
    env['db'].commit()
    assert client.get(f"/api/management/attendance?day={body['day']}").status_code == 403
    assert client.put('/api/management/attendance', json=body).status_code == 403
    assert client.get('/api/management/overview').json()['attendance_today'] is None
    assert env['db'].query(StaffAttendance).count() == 1
    configure(env)
    assert client.get(f"/api/management/attendance?day={body['day']}").json()['items'][0]['attendance']['status'] == 'PRESENT'
