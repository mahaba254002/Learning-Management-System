"""Isolated login HTTP tests; external services are replaced."""
import pytest
from test_teaching import env
from app.core.security import hash_password
from app.core import rate_limit as limiter
from app.models.user import UserRole, UserStatus
from app.models.institution import InstitutionStatus


@pytest.fixture(autouse=True)
def redis_stub(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, "incr", lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, "expire", lambda *args: True)


def credentials(env, who):
    row = env[who]
    row.password_hash = hash_password("Valid-password-123!")
    env["db"].commit()
    return {"email": row.email, "password": "Valid-password-123!"}


@pytest.mark.parametrize("who,path", [("teacher", "/api/auth/teacher/login"), ("admin", "/api/auth/login"), ("pupil", "/api/auth/student/login")])
@pytest.mark.parametrize("uppercase", [False, True])
def test_login_identity_session_and_tenant(env, who, path, uppercase):
    body = credentials(env, who)
    body["email"] = env[who].email.upper() if uppercase else env[who].email
    c = env["client"]
    result = c.post(path, json={**body, "remember_me": False})
    assert result.status_code == 200
    assert result.json()["user"]["id"] == str(env[who].id)
    assert result.headers["cache-control"] == "no-store"
    cookies = result.headers.get_list("set-cookie")
    assert len(cookies) == 3 and all("Max-Age" not in cookie for cookie in cookies)
    assert "HttpOnly" in cookies[0] and "SameSite=lax" in cookies[0]
    assert c.get("/api/me").json()["id"] == str(env[who].id)
    result = c.post(path, json={**body, "remember_me": True})
    assert all("Max-Age=" in cookie for cookie in result.headers.get_list("set-cookie"))


@pytest.mark.parametrize("who,path", [("teacher", "/api/auth/login"), ("admin", "/api/auth/teacher/login"), ("pupil", "/api/auth/login"), ("pupil", "/api/auth/teacher/login"), ("teacher", "/api/auth/student/login"), ("admin", "/api/auth/student/login")])
def test_role_boundaries_and_generic_errors(env, who, path):
    body = credentials(env, who)
    c = env["client"]
    result = c.post(path, json=body)
    missing = c.post(path, json={**body, "email": "missing@example.test"})
    wrong = c.post(path, json={**body, "password": "wrong"})
    assert result.status_code == missing.status_code == wrong.status_code == 401
    assert result.json() == missing.json() == wrong.json()
    assert "set-cookie" not in result.headers


def test_platform_admin_and_forced_password_change(env):
    actor = env["user"]("platform", UserRole.PLATFORM_ADMIN)
    actor.institution_id = None
    actor.must_change_password = True
    env["platform"] = actor
    result = env["client"].post("/api/auth/login", json={"email": actor.email, "password": credentials(env, "platform")["password"]})
    assert result.status_code == 200 and result.json()["must_change_password"]
    assert env["client"].get("/api/platform/usage").status_code == 403


@pytest.mark.parametrize("suspend_institution", [False, True])
def test_suspension_blocks_login(env, suspend_institution):
    body = {"email": env["teacher"].email, "password": credentials(env, "teacher")["password"]}
    if suspend_institution:
        env["institutions"][0].status = InstitutionStatus.SUSPENDED
    else:
        env["teacher"].status = UserStatus.SUSPENDED
    env["db"].commit()
    result = env["client"].post("/api/auth/teacher/login", json=body)
    assert result.status_code == 403 and "set-cookie" not in result.headers


@pytest.mark.parametrize("path", ["/api/auth/login", "/api/auth/teacher/login", "/api/auth/student/login"])
def test_username_rejected(env, path):
    result = env["client"].post(path, json={"username": env["teacher"].username, "password": "ignored"})
    assert result.status_code == 422 and "set-cookie" not in result.headers


def test_limits_shared_across_doors_and_fail_closed(env, monkeypatch):
    keys = []
    def increment(key):
        keys.append(key)
        return 1
    monkeypatch.setattr(limiter.redis_client, "incr", increment)
    for path in ["/api/auth/login", "/api/auth/teacher/login", "/api/auth/student/login"]:
        env["client"].post(path, json={"email": "missing@example.test", "password": "invalid"})
    assert len(set(keys)) == 1
    monkeypatch.setattr(limiter.redis_client, "incr", lambda key: 100000)
    assert env["client"].post("/api/auth/login", json={"email": "x@example.test", "password": "x"}).status_code == 429
    def unavailable(key):
        raise limiter.redis_lib.ConnectionError("test unavailable")
    monkeypatch.setattr(limiter.redis_client, "incr", unavailable)
    result = env["client"].post("/api/auth/login", json={"email": "x@example.test", "password": "x"})
    assert result.status_code == 503 and result.headers["retry-after"] == "60"


def test_unknown_email_uses_one_password_verification(env, monkeypatch):
    from app.api.routes import auth
    calls = []
    monkeypatch.setattr(auth, "verify_password", lambda password, hashed: calls.append(hashed) or False)
    result = env["client"].post("/api/auth/login", json={"email": "absent@example.test", "password": "wrong"})
    assert result.status_code == 401 and calls == [auth._DUMMY_PASSWORD_HASH]


def test_password_recovery_normalizes_email(env, monkeypatch):
    from app.api.routes import auth
    deliveries = []
    monkeypatch.setattr(auth, "generate_verification_code", lambda **kwargs: deliveries.append(kwargs))
    result = env["client"].post("/api/auth/student/forgot-password", json={"email": env["pupil"].email.upper()})
    assert result.status_code == 200
    assert deliveries[0]["user_id"] == env["pupil"].id
