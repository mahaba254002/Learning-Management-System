"""Phase 1 hardening: client IP trust, account throttling, sessions, resets,
delegated credentials, workspace reasons, enrolment control and config."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from starlette.requests import Request

from test_teaching import env, path
from test_workspace_access import actor_client, enter, platform
from app.core import client_ip as client_ip_module
from app.core import rate_limit as limiter
from app.core.config import Settings
from app.core.security import hash_password
from app.models.academic import Enrollment, Student
from app.models.audit import AuditEvent
from app.models.pilot import AuthSession
from app.models.user import User, UserRole, UserStatus
from app.models.verification_code import VerificationCode, VerificationPurpose

PASSWORD = "Hardening-password-123!"


@pytest.fixture(autouse=True)
def rate_stub(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, "incr", lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, "expire", lambda *args: True)


def request_with(headers, peer="198.51.100.20"):
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": raw, "client": (peer, 443)})


def login(env, who="teacher", door="/api/auth/teacher/login"):
    user = env[who]
    user.password_hash = hash_password(PASSWORD)
    env["db"].commit()
    c = env["client"]
    c.cookies.clear()
    result = c.post(door, json=dict(email=user.email, password=PASSWORD))
    assert result.status_code == 200, result.text
    c.headers["X-CSRF-Token"] = c.cookies["csrf_token"]
    return c


# Client IP -------------------------------------------------------------------

def test_client_ip_header_is_trusted_only_with_the_shared_secret(monkeypatch):
    monkeypatch.setattr(client_ip_module.settings, "PROXY_SHARED_SECRET", "s" * 40)
    forwarded = {"X-Skynet-Client-IP": "203.0.113.9"}
    assert client_ip_module.client_ip(request_with(forwarded)) == "198.51.100.20"
    assert client_ip_module.client_ip(request_with({**forwarded, "X-Skynet-Proxy-Secret": "wrong"})) == "198.51.100.20"
    trusted = {**forwarded, "X-Skynet-Proxy-Secret": "s" * 40}
    assert client_ip_module.client_ip(request_with(trusted)) == "203.0.113.9"
    assert client_ip_module.client_ip(request_with({**trusted, "X-Skynet-Client-IP": "not-an-ip"})) == "198.51.100.20"


def test_client_ip_header_is_ignored_when_no_secret_is_configured(monkeypatch):
    monkeypatch.setattr(client_ip_module.settings, "PROXY_SHARED_SECRET", "")
    spoofed = {"X-Skynet-Client-IP": "203.0.113.9", "X-Skynet-Proxy-Secret": ""}
    assert client_ip_module.client_ip(request_with(spoofed)) == "198.51.100.20"


# Login throttling and audit --------------------------------------------------

def test_one_account_is_limited_across_addresses(env, monkeypatch):
    monkeypatch.setattr(limiter.redis_client, "incr", lambda key: 10_000 if ":account:" in key else 1)
    result = env["client"].post("/api/auth/teacher/login", json=dict(email=env["teacher"].email, password="wrong"))
    assert result.status_code == 429


def test_sign_in_events_are_audited_without_secrets(env):
    env["teacher"].password_hash = hash_password(PASSWORD)
    env["db"].commit()
    c = env["client"]
    assert c.post("/api/auth/teacher/login", json=dict(email=env["teacher"].email, password="Wrong-password-1!")).status_code == 401
    assert c.post("/api/auth/login", json=dict(email=env["teacher"].email, password=PASSWORD)).status_code == 401
    assert c.post("/api/auth/teacher/login", json=dict(email=env["teacher"].email, password=PASSWORD)).status_code == 200
    events = env["db"].query(AuditEvent).filter(AuditEvent.actor_id == env["teacher"].id).all()
    assert sorted(e.action for e in events) == ["auth.login", "auth.login_failed", "auth.login_failed"]
    assert all(PASSWORD not in e.detail for e in events)


# Sessions --------------------------------------------------------------------

def test_reusing_a_rotated_refresh_token_ends_the_session(env):
    c = login(env)
    stolen = c.cookies["refresh_token"]
    assert c.post("/api/auth/refresh").status_code == 200
    rotated = c.cookies["refresh_token"]
    c.headers["X-CSRF-Token"] = c.cookies["csrf_token"]
    c.cookies.set("refresh_token", stolen, domain="testserver.local", path="/")
    assert c.post("/api/auth/refresh").status_code == 401
    session = env["db"].query(AuthSession).filter_by(user_id=env["teacher"].id).one()
    env["db"].refresh(session)
    assert session.revoked
    c.cookies.set("refresh_token", rotated, domain="testserver.local", path="/")
    assert c.post("/api/auth/refresh").status_code == 401
    assert env["db"].query(AuditEvent).filter_by(action="auth.refresh_reuse").count() == 1


# Password resets -------------------------------------------------------------

def reset_code(env, user, minutes=10):
    row = VerificationCode(user_id=user.id, purpose=VerificationPurpose.PASSWORD_RESET, code_hash=hash_password("123456"),
                           payload={"user_id": str(user.id), "role": user.role.value},
                           expires_at=datetime.now(timezone.utc) + timedelta(minutes=minutes))
    env["db"].add(row)
    env["db"].commit()
    return row


def reset(env, row, door="/api/auth/teacher/reset-password"):
    return env["client"].post(door, json=dict(verification_id=str(row.id), code="123456",
                                              new_password=PASSWORD, confirm_password=PASSWORD))


def test_a_new_reset_request_retires_older_codes(env, monkeypatch):
    from app.api.routes import auth
    older = reset_code(env, env["teacher"])
    monkeypatch.setattr(auth, "generate_verification_code", lambda **kwargs: None)
    assert env["client"].post("/api/auth/teacher/forgot-password", json=dict(email=env["teacher"].email)).status_code == 200
    env["db"].refresh(older)
    assert older.consumed_at is not None
    assert reset(env, older).status_code == 400


def test_completing_a_reset_retires_every_outstanding_code_and_is_audited(env):
    first, second = reset_code(env, env["teacher"]), reset_code(env, env["teacher"])
    assert reset(env, second).status_code == 200
    env["db"].refresh(first)
    assert first.consumed_at is not None
    assert env["db"].query(AuditEvent).filter_by(action="auth.password_reset", actor_id=env["teacher"].id).count() == 1


def test_a_suspended_account_cannot_complete_a_reset(env):
    row = reset_code(env, env["teacher"])
    env["teacher"].status = UserStatus.SUSPENDED
    env["db"].commit()
    assert reset(env, row).status_code == 400


def test_password_inputs_are_length_capped(env):
    c = login(env)
    huge = "Aa1!" * 400
    result = c.post("/api/auth/change-password", json=dict(current_password=PASSWORD, new_password=huge, confirm_password=huge))
    assert result.status_code == 422


# Delegated workspaces --------------------------------------------------------

def test_platform_admin_must_give_a_reason_to_open_a_workspace(env):
    client = actor_client(env, platform(env))
    result = client.post("/api/workspace-access/start", json={"target_user_id": str(env["admin"].id), "reason": "short"})
    assert result.status_code == 422
    result = client.post("/api/workspace-access/start", json={"target_user_id": str(env["admin"].id), "reason": "Support ticket 4821 about missing marks"})
    assert result.status_code == 200
    entered = env["db"].query(AuditEvent).filter_by(action="workspace.entered").one()
    assert "Support ticket 4821" in entered.detail


def test_institution_admins_do_not_need_a_reason_for_read_only_views(env):
    client = actor_client(env, env["admin"])
    assert client.post("/api/workspace-access/start", json={"target_user_id": str(env["teacher"].id)}).status_code == 200


@pytest.mark.parametrize("method,route", [
    ("post", "/api/institution/students/{pupil}/reset-password"),
    ("put", "/api/institution/students/{pupil}/login"),
    ("post", "/api/teaching/classes/{cls}/students"),
    ("post", "/api/institution/student-imports/commit"),
    ("post", "/api/institution/invitations/{invite}/approve"),
])
def test_credentials_cannot_be_issued_inside_a_delegated_workspace(env, method, route):
    client, _ = enter(env, platform(env), env["admin"])
    url = route.format(pupil=env["pupil"].id, cls=env["cls"].id, invite=uuid.uuid4())
    before = env["pupil"].password_hash
    result = getattr(client, method)(url, json={})
    assert result.status_code == 403, (url, result.status_code, result.text)
    assert "own workspace" in result.json()["detail"]
    env["db"].refresh(env["pupil"])
    assert env["pupil"].password_hash == before


# Enrolment -------------------------------------------------------------------

def new_student(env, admission="A777"):
    user = env["user"](f"new-{admission}", UserRole.STUDENT)
    row = Student(institution_id=user.institution_id, user_id=user.id, admission_number=admission)
    env["db"].add(row)
    env["db"].commit()
    return row


def test_supervisors_cannot_bring_new_students_into_their_class(env):
    student = new_student(env)
    result = env["as_user"](env["supervisor"]).post(path(env, "enrollments"), json={"admission_number": "A777"})
    assert result.status_code == 403
    assert env["db"].query(Enrollment).filter_by(student_id=student.id).count() == 0


def test_admins_enrol_new_students_and_changes_are_audited(env):
    student = new_student(env)
    admin = env["as_user"](env["admin"])
    assert admin.post(path(env, "enrollments"), json={"admission_number": "A777"}).status_code == 200
    supervisor = env["as_user"](env["supervisor"])
    assert supervisor.delete(path(env, f"enrollments/{student.id}")).status_code == 200
    assert supervisor.post(path(env, "enrollments"), json={"admission_number": "A777"}).status_code == 200
    actions = [e.action for e in env["db"].query(AuditEvent).order_by(AuditEvent.created_at).all()]
    assert actions.count("enrollment.added") == 2 and actions.count("enrollment.removed") == 1


# Configuration ---------------------------------------------------------------

def test_settings_fail_closed(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    base = dict(DATABASE_URL="sqlite://", _env_file=None)
    with pytest.raises(ValueError):
        Settings(**base, JWT_SECRET_KEY="x" * 40, ENVIRONMENT="prod")
    with pytest.raises(ValueError):
        Settings(**base, JWT_SECRET_KEY="too-short", ENVIRONMENT="production")
    with pytest.raises(ValueError):
        Settings(**base, JWT_SECRET_KEY="x" * 40, ENVIRONMENT="production", PROXY_SHARED_SECRET="short")
    assert Settings(**base, JWT_SECRET_KEY="x" * 40).ENVIRONMENT == "production"
    assert Settings(**base, JWT_SECRET_KEY="dev", ENVIRONMENT="development").is_development
