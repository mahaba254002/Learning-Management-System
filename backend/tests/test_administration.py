import pytest
from test_teaching import env
from app.models.user import UserRole, UserStatus
from app.models.audit import AuditEvent
from app.models.institution import InstitutionStatus
from app.main import app


def platform(env):
    row = env['user']('platform', UserRole.PLATFORM_ADMIN)
    row.institution_id = None
    env['db'].commit()
    return row


def test_admin_overview_settings_and_tenant_boundaries(env):
    c = env['as_user'](env['admin'])
    data = c.get('/api/institution/overview').json()
    assert data['classes'] == 1 and data['subjects'] == 1 and data['students'] == 1
    assert data['institution']['id'] == str(env['cls'].institution_id)
    body = {'name': 'Updated school', 'country': 'Kenya', 'website': 'https://example.test'}
    assert c.put('/api/institution/settings', json=body).status_code == 200
    assert c.get('/api/institution/settings').json()['name'] == 'Updated school'
    assert c.put('/api/institution/settings', json={**body, 'institution_id': str(env['other_cls'].institution_id)}).status_code == 422
    assert c.put('/api/institution/settings', json={**body, 'status': 'ACTIVE'}).status_code == 422
    assert c.get('/api/platform/users').status_code == 403
    assert c.put(f"/api/institution/users/{env['other_pupil'].id}/status", json={'status': 'SUSPENDED'}).status_code == 404
    assert env['as_user'](env['teacher']).get('/api/institution/overview').status_code == 403


def test_search_pagination_and_sensitive_fields(env):
    c = env['as_user'](env['admin'])
    result = c.get('/api/institution/users?role=STUDENT&limit=1').json()
    assert result['total'] == 1 and result['items'][0]['username'] == 'pupil'
    assert 'password_hash' not in result['items'][0]
    assert 'password_changed_at' not in result['items'][0]
    assert c.get('/api/institution/users?search=%25').json()['total'] == 0
    assert c.get('/api/institution/users?limit=101').status_code == 422
    assert c.get('/api/institution/users?offset=-1').status_code == 422
    assert c.get('/api/institution/users?role=STUDENT&offset=1').json()['items'] == []
    assert env['as_user'](platform(env)).get('/api/platform/users?role=STUDENT').json()['total'] == 2


def test_suspend_reactivate_invalidates_old_session_and_logs(env):
    c = env['as_user'](env['pupil'])
    old = c.cookies.get('access_token')
    c = env['as_user'](env['admin'])
    url = f"/api/institution/users/{env['pupil'].id}/status"
    assert c.put(url, json={'status': 'SUSPENDED'}).status_code == 200
    assert env['pupil'].status == UserStatus.SUSPENDED
    assert c.put(url, json={'status': 'ACTIVE'}).status_code == 200
    c.cookies.set('access_token', old)
    assert c.get('/api/student/profile').status_code == 401
    c = env['as_user'](env['admin'])
    events = c.get('/api/institution/audit-logs').json()
    assert events['total'] == 2
    assert {r['detail'] for r in events['items']} == {'ACTIVE', 'SUSPENDED'}
    assert c.put(f"/api/institution/users/{env['admin'].id}/status", json={'status': 'SUSPENDED'}).status_code == 403


def test_platform_controls_and_audit_scopes(env):
    actor = platform(env)
    c = env['as_user'](actor)
    assert c.get('/api/platform/usage').json()['institutions'] == 2
    assert c.put(f'/api/platform/users/{actor.id}/status', json={'status': 'SUSPENDED'}).status_code == 403
    url = f"/api/platform/institutions/{env['other_cls'].institution_id}/status"
    assert c.put(url, json={'status': 'SUSPENDED'}).status_code == 200
    assert env['as_user'](env['outsider']).get('/api/teaching/classes').status_code == 401
    c = env['as_user'](actor)
    assert c.put(url, json={'status': 'ACTIVE'}).status_code == 200
    assert c.get('/api/platform/audit-logs').json()['total'] == 2
    assert env['as_user'](env['admin']).get('/api/institution/audit-logs').json()['total'] == 0
    env['institutions'][1].status = InstitutionStatus.ARCHIVED
    env['db'].commit()
    assert env['as_user'](actor).put(url, json={'status': 'ACTIVE'}).status_code == 409
    assert env['db'].query(AuditEvent).count() == 2


@pytest.mark.parametrize('path', ['/api/platform/users', '/api/platform/usage', '/api/platform/audit-logs', '/api/institution/users', '/api/institution/settings', '/api/institution/audit-logs'])
def test_students_cannot_access_admin_endpoints(env, path):
    assert env['as_user'](env['pupil']).get(path).status_code == 403


def test_csrf_and_forced_password_are_enforced(env):
    c = env['as_user'](env['admin'])
    del c.headers['X-CSRF-Token']
    assert c.put('/api/institution/settings', json={'name': 'School', 'country': 'Kenya'}).status_code == 403
    env['admin'].must_change_password = True
    env['db'].commit()
    assert c.get('/api/institution/overview').status_code == 403


def test_no_duplicate_route_registrations():
    keys = [(r.path, method) for r in app.routes for method in getattr(r, 'methods', [])]
    assert len(keys) == len(set(keys))


def test_platform_create_admin_and_archive_audited_without_email(env, monkeypatch):
    from uuid import uuid4
    from fastapi import Response
    from app.api.routes import platform as routes
    from app.core.deps import AuthContext
    from app.schemas.institution import InstitutionAdminCreateRequest, ConfirmCodeRequest
    actor = platform(env)
    ctx = AuthContext(actor.id, None, UserRole.PLATFORM_ADMIN, False)
    response = Response()
    created = routes.create_institution_admin(env['cls'].institution_id,
        InstitutionAdminCreateRequest(first_name='New', last_name='Admin', email='new-admin@example.test'), response, env['db'], ctx)
    assert created.temporary_password and response.headers['cache-control'] == 'no-store'
    from app.models.user import User
    account = env['db'].get(User, created.id)
    assert account.must_change_password and account.role == UserRole.INSTITUTION_ADMIN
    monkeypatch.setattr(routes, 'confirm_verification_code', lambda **kwargs: {'institution_id': str(env['cls'].institution_id)})
    result = routes.confirm_archive_institution(ConfirmCodeRequest(verification_id=uuid4(), code='123456'), env['db'], ctx)
    assert result.status == InstitutionStatus.ARCHIVED
    assert {r.action for r in env['db'].query(AuditEvent).all()} == {'institution.admin_created', 'institution.archived'}
    assert env['as_user'](env['admin']).get('/api/institution/overview').status_code == 401


def test_admin_email_required_and_invalid_uuid_rejected(env):
    from pydantic import ValidationError
    from app.schemas.institution import InstitutionAdminCreateRequest
    with pytest.raises(ValidationError):
        InstitutionAdminCreateRequest(first_name='New', last_name='Admin')
    c = env['as_user'](platform(env))
    assert c.put('/api/platform/institutions/not-a-uuid/status', json={'status': 'ACTIVE'}).status_code == 422


def test_institution_admin_can_oversee_only_own_academic_records(env):
    c = env['as_user'](env['admin'])
    assert c.get(f"/api/teaching/subjects/{env['subject'].id}/coursework").status_code == 200
    assert c.get(f"/api/teaching/subjects/{env['other_subject'].id}/coursework").status_code == 404
    assert c.get(f"/api/teaching/coursework/{env['other_work'].id}/submissions").status_code == 404


def test_orphan_student_cannot_receive_a_session_or_enter_portal(env, monkeypatch):
    from fastapi import HTTPException, Response
    from app.api.routes import auth
    from app.schemas.auth import LoginRequest
    # Remove the profile first: real production orphan has no valid tenant profile.
    from app.models.academic import Enrollment, Student
    env['db'].query(Enrollment).filter_by(student_id=env['student'].id).delete()
    env['db'].delete(env['student'])
    env['db'].flush()
    env['pupil'].institution_id = None
    env['db'].commit()
    monkeypatch.setattr(auth, 'verify_password', lambda *args: True)
    with pytest.raises(HTTPException) as error:
        auth._authenticate(LoginRequest(username='pupil', password='Test-password1!'), Response(), env['db'], allowed_roles=auth.STUDENT_ROLES)
    assert error.value.status_code == 403
    assert env['as_user'](env['pupil']).get('/api/me').status_code == 401
