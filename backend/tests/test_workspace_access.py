"""Real HTTP access checks using isolated fixtures, never live accounts."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from test_teaching import env

from app.core.config import settings
from app.core.security import create_access_token, create_workspace_token
from app.models.academic import Coursework, Enrollment
from app.models.audit import AuditEvent
from app.models.learning import Submission
from app.models.teacher import Teacher, TeacherStatus
from app.models.user import UserRole, UserStatus


def actor_client(env, who):
    client = env["as_user"](who)
    client.headers.pop("X-Workspace-Token", None)
    return client


def enter(env, actor, target):
    client = actor_client(env, actor)
    result = client.post("/api/workspace-access/start", json={"target_user_id": str(target.id)})
    assert result.status_code == 200, result.text
    data = result.json()
    client.headers["X-Workspace-Token"] = data["token"]
    return client, data


def platform(env):
    row = env["user"]("platform-access", UserRole.PLATFORM_ADMIN)
    row.institution_id = None
    env["db"].commit()
    return row


@pytest.mark.parametrize("who", ["teacher", "supervisor"])
def test_teacher_student_view_preserves_real_session_and_records_audit(env, who):
    client, data = enter(env, env[who], env["pupil"])
    assert data["read_only"] is True and data["actor"]["id"] == str(env[who].id)
    assert client.get("/api/me").json()["id"] == str(env["pupil"].id)
    assert client.get("/api/student/profile").json()["email"] == env["pupil"].email
    result = client.post("/api/workspace-access/stop")
    assert result.status_code == 200 and result.json()["id"] == str(env[who].id)
    client.headers.pop("X-Workspace-Token")
    assert client.get("/api/me").json()["id"] == str(env[who].id)
    events = env["db"].query(AuditEvent).all()
    assert {r.action for r in events} == {"workspace.entered", "workspace.exited"}
    assert all(r.actor_id == env[who].id for r in events)


@pytest.mark.parametrize("actor,target", [("unrelated", "pupil"), ("teacher", "other_pupil"), ("teacher", "admin"), ("teacher", "supervisor"), ("pupil", "teacher"), ("admin", "outsider"), ("admin", "other_pupil")])
def test_unauthorised_targets_are_unavailable(env, actor, target):
    result = actor_client(env, env[actor]).post("/api/workspace-access/start", json={"target_user_id": str(env[target].id)})
    assert result.status_code == 404 and "token" not in result.json()


def test_institution_admin_teacher_view_and_class_register_remain_readable(env):
    client, data = enter(env, env["admin"], env["supervisor"])
    assert data["read_only"] is True
    assert client.get("/api/teacher/profile").json()["user_id"] == str(env["supervisor"].id)
    classes = client.get("/api/teaching/classes").json()
    assert classes[0]["can_manage"] is False
    assert classes[0]["can_view_class_register"] is True
    # An admin can drill down from the teacher view; identity remains the real admin.
    result = client.post("/api/workspace-access/start", json={"target_user_id": str(env["pupil"].id)})
    assert result.status_code == 200 and result.json()["actor"]["id"] == str(env["admin"].id)
    assert result.json()["read_only"] is True


@pytest.mark.parametrize("actor,target", [("teacher", "pupil"), ("admin", "pupil")])
def test_readonly_student_cannot_save_submit_or_change_password(env, actor, target):
    env["work"].published = True
    env["db"].commit()
    client, _ = enter(env, env[actor], env[target])
    for submit in [False, True]:
        result = client.put(f"/api/student/assignments/{env['work'].id}/submission",
                            json={"answer": "Forbidden change", "link_url": None, "expected_version": 0, "submit": submit})
        assert result.status_code == 403
    assert env["db"].query(Submission).count() == 0
    result = client.post("/api/auth/change-password", json={"current_password": "x", "new_password": "Changed-password-123!", "confirm_password": "Changed-password-123!"})
    assert result.status_code == 403


def test_readonly_teacher_cannot_create_edit_or_remove(env):
    client, _ = enter(env, env["admin"], env["supervisor"])
    root = f"/api/teaching/classes/{env['cls'].id}"
    assert client.post(root + "/enrollments", json={"admission_number": "A001"}).status_code == 403
    assert client.put(root + f"/students/{env['student'].id}", json={"first_name": "Changed", "last_name": "Name", "phone": "123"}).status_code == 403
    assert client.delete(root + f"/enrollments/{env['student'].id}").status_code == 403
    assert env["pupil"].first_name == "pupil"
    assert env["db"].query(Enrollment).filter_by(student_id=env["student"].id).one().active


def test_platform_admin_edits_teacher_workspace_and_audit_keeps_real_actor(env):
    actor = platform(env)
    client, data = enter(env, actor, env["teacher"])
    assert data["read_only"] is False
    result = client.post(f"/api/teaching/subjects/{env['subject'].id}/coursework",
                         json={"title": "Platform-created work", "instructions": "Complete this work", "max_score": 25, "published": True})
    assert result.status_code == 201, result.text
    assert env["db"].query(Coursework).filter_by(title="Platform-created work").count() == 1
    event = env["db"].query(AuditEvent).filter_by(action="workspace.mutation_attempt").one()
    assert event.actor_id == actor.id and event.target_id == str(env["teacher"].id)


def test_platform_admin_edits_student_workspace_and_can_enter_other_institution(env):
    actor = platform(env)
    env["work"].published = True
    env["db"].commit()
    client, data = enter(env, actor, env["pupil"])
    result = client.put(f"/api/student/assignments/{env['work'].id}/submission",
                        json={"answer": "Saved by platform administrator", "expected_version": 0, "submit": False})
    assert result.status_code == 200, result.text
    assert env["db"].query(Submission).one().answer == "Saved by platform administrator"
    assert enter(env, actor, env["outsider"])[1]["read_only"] is False


def test_platform_admin_enters_admin_and_existing_audits_attribute_real_actor(env):
    actor = platform(env)
    client, _ = enter(env, actor, env["admin"])
    result = client.post("/api/teaching/classes", json={"name": "Platform new class", "academic_year": "2026"})
    assert result.status_code == 201, result.text
    event = env["db"].query(AuditEvent).filter_by(action="class.created").one()
    assert event.actor_id == actor.id and str(env["admin"].id) in event.detail


def test_platform_workspace_cannot_change_target_account_credentials(env):
    client, _ = enter(env, platform(env), env["teacher"])
    original_hash = env["teacher"].password_hash
    result = client.post("/api/auth/change-password", json={"current_password": "x", "new_password": "Changed-password-123!", "confirm_password": "Changed-password-123!"})
    assert result.status_code == 403 and env["teacher"].password_hash == original_hash


def test_workspace_grants_cannot_be_forged_replayed_or_replaced_with_auth_token(env):
    client, data = enter(env, env["admin"], env["teacher"])
    for value in [data["token"] + "corrupt", create_access_token(user_id=env["admin"].id, institution_id=env["admin"].institution_id, role="INSTITUTION_ADMIN")]:
        client.headers["X-Workspace-Token"] = value
        assert client.get("/api/me").status_code == 401
    client = actor_client(env, env["pupil"])
    client.headers["X-Workspace-Token"] = data["token"]
    assert client.get("/api/me").status_code == 401
    client = actor_client(env, env["teacher"])
    assert client.post("/api/workspace-access/start", json={"target_user_id": str(env["pupil"].id), "read_only": False}).status_code == 422


def test_workspace_expiration_and_csrf(env):
    client = actor_client(env, env["teacher"])
    token = jwt.encode({"sub": str(env["teacher"].id), "target": str(env["pupil"].id), "type": "workspace",
                        "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    client.headers["X-Workspace-Token"] = token
    assert client.get("/api/student/profile").status_code == 401
    client.headers.pop("X-Workspace-Token")
    client.headers.pop("X-CSRF-Token")
    assert client.post("/api/workspace-access/start", json={"target_user_id": str(env["pupil"].id)}).status_code == 403


@pytest.mark.parametrize("revocation", ["enrollment", "target", "teacher"])
def test_live_permissions_rechecked_on_every_request(env, revocation):
    client, _ = enter(env, env["teacher"], env["pupil"])
    if revocation == "enrollment":
        env["db"].query(Enrollment).filter_by(student_id=env["student"].id).one().active = False
    elif revocation == "target":
        env["pupil"].status = UserStatus.SUSPENDED
    else:
        env["db"].query(Teacher).filter_by(user_id=env["teacher"].id).one().status = TeacherStatus.SUSPENDED
    env["db"].commit()
    assert client.get("/api/student/profile").status_code == 404


def test_forced_password_checks_apply_to_real_actor_not_observed_student(env):
    env["pupil"].must_change_password = True
    env["db"].commit()
    client, _ = enter(env, env["teacher"], env["pupil"])
    assert client.get("/api/me").json()["must_change_password"] is False
    assert client.get("/api/student/profile").status_code == 200
    env["teacher"].must_change_password = True
    env["db"].commit()
    assert client.get("/api/student/profile").status_code == 403


def test_platform_grant_loses_write_access_on_role_demotion(env):
    actor = platform(env)
    client, _ = enter(env, actor, env["teacher"])
    actor.role, actor.institution_id = UserRole.INSTITUTION_ADMIN, env["cls"].institution_id
    env["db"].commit()
    assert client.post(f"/api/teaching/subjects/{env['subject'].id}/coursework",
                       json={"title": "Denied", "instructions": "No changes", "max_score": 10}).status_code == 403
