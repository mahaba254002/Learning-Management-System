"""Connected pilot workflows: real HTTP permissions, transactions and session revocation."""
import io
import uuid
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from openpyxl import Workbook
from test_teaching import env
from app.core import rate_limit as limiter
from app.core.config import settings
from app.core.security import decode_token, hash_password, verify_password
from app.models.academic import AcademicClass, Attendance, Enrollment, Score, Student
from app.models.pilot import AuthSession, WorkDraft, AcademicYear
from app.models.user import User, UserStatus
from app.models.institution import InstitutionStatus
from sqlalchemy import event


@pytest.fixture(autouse=True)
def rate_stub(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, 'incr', lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, 'expire', lambda *args: True)


def login(env, remember=False):
    user = env['teacher']; user.password_hash = hash_password('Pilot-password-123!'); env['db'].commit()
    c = env['client']; c.cookies.clear()
    response = c.post('/api/auth/teacher/login', json=dict(email=user.email, password='Pilot-password-123!', remember_me=remember))
    assert response.status_code == 200
    c.headers['X-CSRF-Token'] = c.cookies['csrf_token']
    return c, response


def test_refresh_missing_access_rotation_absolute_expiry_and_logout(env):
    c, _ = login(env)
    old_refresh, old_access = c.cookies['refresh_token'], c.cookies['access_token']
    expiry = decode_token(old_refresh)['exp']
    c.cookies.delete('access_token')
    renewed = c.post('/api/auth/refresh')
    assert renewed.status_code == 200
    new_refresh = c.cookies['refresh_token']
    assert new_refresh != old_refresh and decode_token(new_refresh)['exp'] == expiry
    assert all('Max-Age' not in cookie for cookie in renewed.headers.get_list('set-cookie'))
    assert c.get('/api/me').status_code == 200
    c.headers['X-CSRF-Token'] = c.cookies['csrf_token']
    c.cookies.set('refresh_token', old_refresh, domain='testserver.local', path='/')
    assert c.post('/api/auth/refresh').status_code == 401
    c.cookies.set('refresh_token', new_refresh, domain='testserver.local', path='/')
    assert c.post('/api/auth/logout').status_code == 200
    c.cookies.set('access_token', old_access)
    assert c.get('/api/me').status_code == 401
    c.cookies.set('refresh_token', new_refresh)
    c.cookies.set('csrf_token', 'post-logout-test')
    c.headers['X-CSRF-Token'] = 'post-logout-test'
    assert c.post('/api/auth/refresh').status_code == 401


@pytest.mark.parametrize('blocked', ['password', 'user', 'institution', 'expired'])
def test_refresh_cannot_revive_revoked_accounts(env, blocked):
    c, _ = login(env, remember=True)
    if blocked == 'password': env['teacher'].password_changed_at = datetime.now(timezone.utc) + timedelta(seconds=1)
    if blocked == 'user': env['teacher'].status = UserStatus.SUSPENDED
    if blocked == 'institution': env['institutions'][0].status = InstitutionStatus.SUSPENDED
    if blocked == 'expired': env['db'].query(AuthSession).one().expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    env['db'].commit()
    assert c.post('/api/auth/refresh').status_code == 401


def test_refresh_requires_csrf_and_real_refresh_type(env):
    c, _ = login(env)
    c.headers.pop('X-CSRF-Token')
    assert c.post('/api/auth/refresh').status_code == 403
    c.headers['X-CSRF-Token'] = c.cookies['csrf_token']
    c.cookies.set('refresh_token', c.cookies['access_token'], domain='testserver.local', path='/')
    assert c.post('/api/auth/refresh').status_code == 401


def draft_client(env, who='teacher'):
    c = env['as_user'](env[who])
    c.headers['X-Draft-User'] = c.headers['X-Draft-Actor'] = str(env[who].id)
    return c


def test_private_draft_persists_without_publishing_and_rejects_stale_tabs(env):
    c = draft_client(env)
    path = f"/api/drafts/scores/{env['work'].id}"
    assert c.get(path).json()['version'] == 0
    result = c.put(path, json=dict(expected_version=0, data={'some': 'unfinished marks'}))
    assert result.status_code == 200 and result.json()['version'] == 1
    assert env['db'].query(Score).count() == 0
    assert c.get(path).json()['data'] == {'some': 'unfinished marks'}
    assert c.put(path, json=dict(expected_version=0, data={})).status_code == 409
    other = draft_client(env, 'supervisor')
    assert other.get(path).status_code == 404
    other = draft_client(env, 'admin')
    assert other.get(path).json()['data'] is None
    assert env['db'].query(WorkDraft).count() == 1
    other.headers['X-Draft-User'] = str(env['teacher'].id)
    assert other.put(path, json=dict(expected_version=0, data={})).status_code == 409


def test_student_draft_does_not_become_submission(env):
    env['work'].published = True; env['db'].commit()
    c = draft_client(env, 'pupil')
    path = f"/api/drafts/submission/{env['work'].id}"
    assert c.put(path, json=dict(expected_version=0, data={'answer': 'Still working'})).status_code == 200
    from app.models.learning import Submission
    assert env['db'].query(Submission).count() == 0
    assert c.put(f"/api/drafts/scores/{env['work'].id}", json=dict(expected_version=0, data={})).status_code == 403


def import_body(env):
    return dict(class_id=str(env['cls'].id), rows=[dict(first_name='Import', last_name='Pupil', admission_number='IMP-001', login_method='STUDENT_ID', login_id='IMP-0001')])


def test_reviewed_student_import_connects_login_and_class_roster(env):
    c = env['as_user'](env['admin']); body = import_body(env)
    review = c.post('/api/institution/student-imports/preview', json=body)
    assert review.status_code == 200 and not review.json()['errors']
    assert env['db'].query(Student).count() == 2
    result = c.post('/api/institution/student-imports/commit', json={**body, 'preview_token': review.json()['preview_token']})
    assert result.status_code == 200 and result.json()['created'] == 1
    credential = result.json()['credentials'][0]
    user = env['db'].query(User).filter_by(student_login_id='IMP-0001').one()
    assert user.must_change_password and verify_password(credential['temporary_password'], user.password_hash)
    assert len(c.get(f"/api/teaching/classes/{env['cls'].id}/students").json()) == 2
    assert c.post('/api/auth/student/login', json=dict(student_id='IMP-0001', password=credential['temporary_password'])).status_code == 200
    assert c.get('/api/student/subjects').status_code == 403  # mandatory first password change


def test_import_validation_and_stale_preview_are_atomic(env):
    c = env['as_user'](env['admin']); body = import_body(env)
    duplicate = {**body, 'rows': body['rows'] * 2}
    assert c.post('/api/institution/student-imports/preview', json=duplicate).json()['preview_token'] is None
    token = c.post('/api/institution/student-imports/preview', json=body).json()['preview_token']
    changed = {**body, 'rows': [{**body['rows'][0], 'first_name': 'Tampered'}], 'preview_token': token}
    assert c.post('/api/institution/student-imports/commit', json=changed).status_code == 409
    env['other_pupil'].student_login_id = 'IMP-0001'; env['db'].commit()
    assert c.post('/api/institution/student-imports/commit', json={**body, 'preview_token': token}).status_code == 409
    assert env['db'].query(Student).count() == 2
    assert env['db'].query(User).filter_by(first_name='Import').count() == 0


def test_import_database_failure_rolls_back_the_whole_batch(env):
    c = env['as_user'](env['admin']); body = import_body(env)
    body['rows'].append({**body['rows'][0], 'admission_number': 'IMP-002', 'login_id': 'IMP-0002'})
    token = c.post('/api/institution/student-imports/preview', json=body).json()['preview_token']
    # Simulate a concurrent uniqueness failure after the first row was flushed.
    db = env['db']
    db.connection().exec_driver_sql("CREATE TRIGGER reject_second_import BEFORE INSERT ON students WHEN NEW.admission_number = 'IMP-002' BEGIN SELECT RAISE(ABORT, 'simulated conflict'); END")
    db.commit()
    response = c.post('/api/institution/student-imports/commit', json={**body, 'preview_token': token})
    assert response.status_code == 409
    assert db.query(Student).count() == 2
    assert db.query(User).filter(User.student_login_id.in_(['IMP-0001', 'IMP-0002'])).count() == 0


def test_refresh_preserves_mandatory_password_change(env):
    c, _ = login(env)
    env['teacher'].must_change_password = True; env['db'].commit()
    assert c.post('/api/auth/refresh').status_code == 200
    assert c.get('/api/teaching/subjects').status_code == 403


def test_assessment_rejects_an_old_edit_version(env):
    c = env['as_user'](env['teacher'])
    body = dict(title='Stale title', instructions='Changed', max_score=20, expected_updated_at='1999-01-01T00:00:00')
    assert c.put(f"/api/teaching/coursework/{env['work'].id}", json=body).status_code == 409
    assert env['work'].title == 'Algebra'


@pytest.mark.parametrize('who', ['teacher', 'pupil', 'outsider'])
def test_import_admin_boundary(env, who):
    c = env['as_user'](env[who])
    assert c.post('/api/institution/student-imports/preview', json=import_body(env)).status_code == 403


def test_import_file_parsing_csv_xlsx_and_formula_rejection(env):
    c = env['as_user'](env['admin'])
    header = ['first_name', 'last_name', 'admission_number', 'login_method', 'login_id']
    csv = ','.join(header) + '\nMary,Example,0001,STUDENT_ID,0001\n'
    result = c.post('/api/institution/student-imports/parse?filename=students.csv', content=csv)
    assert result.status_code == 200 and result.json()['rows'][0]['admission_number'] == '0001'
    book = Workbook(); sheet = book.active; sheet.append(header); sheet.append(['Mary', 'Example', '0001', 'STUDENT_ID', '0001'])
    stream = io.BytesIO(); book.save(stream)
    result = c.post('/api/institution/student-imports/parse?filename=students.xlsx', content=stream.getvalue())
    assert result.status_code == 200 and result.json()['rows'][0]['login_id'] == '0001'
    sheet['A2'] = '=1+1'; stream = io.BytesIO(); book.save(stream)
    assert c.post('/api/institution/student-imports/parse?filename=students.xlsx', content=stream.getvalue()).status_code == 422
    assert c.post('/api/institution/student-imports/parse?filename=students.csv', content=csv + 'x,' * 9).status_code == 422


def create_year(c, name='2026', start='2026-01-01', end='2026-12-31'):
    result = c.post('/api/institution/academic-years', json=dict(name=name, start_date=start, end_date=end))
    assert result.status_code == 201, result.text
    identity = result.json()['id']
    assert c.post(f'/api/institution/academic-years/{identity}/periods', json=dict(name='Term 1', start_date=start, end_date=end)).status_code == 201
    return identity


def activate(c, identity, name='2026'):
    return c.post(f'/api/institution/academic-years/{identity}/transition', json=dict(status='ACTIVE', confirmation=f'ACTIVE {name}'))


def close(c, identity, name='2026'):
    return c.post(f'/api/institution/academic-years/{identity}/transition', json=dict(status='CLOSED', confirmation=f'CLOSED {name}'))


def test_calendar_dates_overlaps_and_single_active_year(env):
    c = env['as_user'](env['admin'])
    year = create_year(c)
    assert activate(c, year).status_code == 200
    assert c.post('/api/institution/academic-years', json=dict(name='Overlap', start_date='2026-12-01', end_date='2027-06-01')).status_code == 409
    assert c.post(f'/api/institution/academic-years/{year}/periods', json=dict(name='Outside', start_date='2027-01-01', end_date='2027-01-02')).status_code == 422
    assert c.post(f'/api/institution/academic-years/{year}/periods', json=dict(name='Overlap', start_date='2026-01-01', end_date='2026-02-01')).status_code == 409
    next_year = create_year(c, '2027', '2027-01-01', '2027-12-31')
    assert activate(c, next_year, '2027').status_code == 409
    assert close(c, year).status_code == 200
    assert c.get('/api/institution/overview').json()['active_enrollments'] == 0
    teacher = env['as_user'](env['teacher'])
    assert teacher.get('/api/teaching/overview').json()['enrollment_by_class'] == []
    c = env['as_user'](env['admin'])
    assert activate(c, next_year, '2027').status_code == 200


def test_closure_requires_released_complete_marks_and_locks_academic_writes(env):
    c = env['as_user'](env['admin']); year = create_year(c); activate(c, year)
    env['work'].published = True; env['db'].commit()
    assert close(c, year).status_code == 409
    env['work'].grades_released = True; env['db'].commit()
    assert close(c, year).status_code == 409
    env['db'].add(Score(institution_id=env['cls'].institution_id, coursework_id=env['work'].id, student_id=env['student'].id, score=10)); env['db'].commit()
    assert close(c, year).status_code == 200
    assert c.get(f"/api/teaching/classes/{env['cls'].id}/students").status_code == 200
    assert c.post(f"/api/teaching/classes/{env['cls'].id}/enrollments", json=dict(admission_number='A001')).status_code == 409
    assert c.put(f"/api/teaching/coursework/{env['work'].id}/results-release", json=dict(released=False)).status_code == 409
    teacher = env['as_user'](env['teacher'])
    # A historical teaching allocation must not grant access to a learner's future workspace.
    assert teacher.post('/api/workspace-access/start', json=dict(target_user_id=str(env['pupil'].id))).status_code == 404
    pupil = env['as_user'](env['pupil'])
    assert pupil.put(f"/api/student/assignments/{env['work'].id}/submission", json=dict(answer='Late write', expected_version=0, submit=False)).status_code == 409


def test_promotion_preserves_original_history_and_blocks_replay(env):
    c = env['as_user'](env['admin']); year = create_year(c); activate(c, year); close(c, year)
    target = create_year(c, '2027', '2027-01-01', '2027-12-31')
    cls = c.post('/api/teaching/classes', json=dict(name='Form 2', academic_year='2027')).json()['id']
    body = dict(target_year_id=target, mappings=[dict(source_class_id=str(env['cls'].id), target_class_id=cls)])
    review = c.post(f'/api/institution/academic-years/{year}/promotion/preview', json=body)
    assert review.status_code == 200 and review.json()['enrollments'] == 1
    result = c.post(f'/api/institution/academic-years/{year}/promotion/commit', json={**body, 'preview_token': review.json()['preview_token']})
    assert result.status_code == 200
    assert env['db'].query(Enrollment).filter_by(student_id=env['student'].id).count() == 2
    assert len(c.get(f'/api/teaching/classes/{cls}/students').json()) == 1
    assert c.post(f'/api/institution/academic-years/{year}/promotion/commit', json={**body, 'preview_token': review.json()['preview_token']}).status_code == 409


def test_promotion_tenant_boundary_and_stale_plan(env):
    c = env['as_user'](env['admin']); year = create_year(c); activate(c, year); close(c, year)
    target = create_year(c, '2027', '2027-01-01', '2027-12-31')
    body = dict(target_year_id=target, mappings=[dict(source_class_id=str(env['cls'].id), target_class_id=str(env['other_cls'].id))])
    assert c.post(f'/api/institution/academic-years/{year}/promotion/preview', json=body).status_code == 404
    body['mappings'][0]['target_class_id'] = None
    token = c.post(f'/api/institution/academic-years/{year}/promotion/preview', json=body).json()['preview_token']
    env['cls'].name = 'Changed after review'; env['db'].commit()
    assert c.post(f'/api/institution/academic-years/{year}/promotion/commit', json={**body, 'preview_token': token}).status_code == 409


def test_register_revision_prevents_overwriting_other_session(env):
    c = env['as_user'](env['supervisor'])
    path = f"/api/teaching/classes/{env['cls'].id}/attendance"
    payload = dict(day='2026-01-01', entries=[dict(student_id=str(env['student'].id), status='PRESENT')], expected_revision='[]')
    assert c.put(path, json=payload).status_code == 200
    payload['entries'][0]['status'] = 'ABSENT'
    assert c.put(path, json=payload).status_code == 409
    assert env['db'].query(Attendance).one().status == 'PRESENT'
