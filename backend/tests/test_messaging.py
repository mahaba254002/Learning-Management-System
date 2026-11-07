"""Phase 8: reviewed parent messages sent with a secret answer, SMS allowance, outbox and delivery reports."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from test_teaching import env  # noqa: F401
from test_workspace_access import platform
from app.core import rate_limit as limiter
from app.core.config import settings
from app.core.security import hash_password
from app.models.academic import Enrollment, Student
from app.models.messaging import GuardianMessage, MessageDelivery, MessagingSecret
from app.models.pilot import AcademicPeriod, AcademicYear
from app.models.records import FeeStatus, Guardian, StudentGuardian
from app.models.user import User, UserRole
from app.services import email_service, sms

PASSWORD = "Correct-horse-battery-9"


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, "incr", lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, "expire", lambda *args: True)


@pytest.fixture
def school(env, monkeypatch):
    db, tenant = env["db"], env["institutions"][0].id
    env["admin"].password_hash = hash_password(PASSWORD)
    year = AcademicYear(institution_id=tenant, name="2026", start_date=date.today() - timedelta(days=100), end_date=date.today() + timedelta(days=100))
    db.add(year); db.flush()
    term = AcademicPeriod(institution_id=tenant, year_id=year.id, name="Term 3", start_date=date.today() - timedelta(days=20), end_date=date.today() + timedelta(days=40))
    sibling_user = User(institution_id=tenant, username="sib", first_name="Faith", last_name="Kamau", email="sib@example.test",
                        role=UserRole.STUDENT, password_hash="x", must_change_password=False)
    db.add_all([term, sibling_user]); db.flush()
    sibling = Student(institution_id=tenant, user_id=sibling_user.id, admission_number="A002")
    db.add(sibling); db.flush()
    db.add(Enrollment(institution_id=tenant, class_id=env["cls"].id, student_id=sibling.id))
    mother = Guardian(institution_id=tenant, full_name="Lucy Wairimu", phone="+254712345678", email="lucy@example.test")
    father = Guardian(institution_id=tenant, full_name="John Kamau", phone="+254722000111")
    db.add_all([mother, father]); db.flush()
    db.add_all([StudentGuardian(institution_id=tenant, student_id=env["student"].id, guardian_id=mother.id, relationship="Mother", is_primary=True),
                StudentGuardian(institution_id=tenant, student_id=env["student"].id, guardian_id=father.id, relationship="Father"),
                StudentGuardian(institution_id=tenant, student_id=sibling.id, guardian_id=mother.id, relationship="Mother", is_primary=True),
                FeeStatus(institution_id=tenant, student_id=env["student"].id, period_id=term.id, status="PARTIAL", balance=Decimal("12500")),
                FeeStatus(institution_id=tenant, student_id=sibling.id, period_id=term.id, status="PAID", balance=Decimal("0"))])
    db.commit()
    sent, emails = [], []
    monkeypatch.setattr(settings, "AT_USERNAME", "sandbox")
    monkeypatch.setattr(settings, "AT_API_KEY", "key")
    monkeypatch.setattr(settings, "AT_CALLBACK_SECRET", "d" * 40)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")

    def fake_send(numbers, message):
        sent.append((tuple(numbers), message))
        return {n: dict(accepted=True, message_id=f"ATX-{len(sent)}-{n[-3:]}", cost=Decimal("0.8"), status="Success") for n in numbers}
    monkeypatch.setattr(sms, "send", fake_send)
    monkeypatch.setattr(email_service, "send_email", lambda **kw: emails.append(kw))
    return dict(term=term, sibling=sibling, sent=sent, emails=emails)


def admin(env):
    return env["as_user"](env["admin"])


def set_secret(env):
    return admin(env).put("/api/messaging/secret", json=dict(password=PASSWORD, question="My first school's town?", answer="  Nyeri "))


def test_sms_parts():
    assert sms.parts("a" * 160) == 1 and sms.parts("a" * 161) == 2 and sms.parts("a" * 306) == 2 and sms.parts("a" * 307) == 3
    assert sms.parts("€" * 80) == 1 and sms.parts("€" * 81) == 2  # Extended characters count twice.
    assert sms.parts("✓" * 70) == 1 and sms.parts("✓" * 71) == 2  # Outside the SMS alphabet: 70 per part.
    assert sms.cost("KES 0.8000") == Decimal("0.8000")


def test_secret_answer_is_hashed_checked_and_locks(env, school):
    assert admin(env).put("/api/messaging/secret", json=dict(password="wrong", question="My first school's town?", answer="Nyeri")).status_code == 403
    assert admin(env).put("/api/messaging/secret", json=dict(password=PASSWORD, question="Is it Nyeri town?", answer="nyeri")).status_code == 422
    assert set_secret(env).status_code == 200
    row = env["db"].get(MessagingSecret, env["admin"].id)
    assert "nyeri" not in row.answer_hash.lower() and row.answer_hash.startswith("$")
    draft = admin(env).post("/api/messaging/messages", json=dict(kind="ANNOUNCEMENT", title="Closing day", template="School closes Friday at noon.")).json()
    for _ in range(5):
        assert admin(env).post(f"/api/messaging/messages/{draft['id']}/send", json=dict(answer="Nakuru")).status_code == 403
    assert admin(env).post(f"/api/messaging/messages/{draft['id']}/send", json=dict(answer="nyeri")).status_code == 423
    owner = env["as_user"](platform(env))
    assert owner.delete(f"/api/platform/institutions/{env['institutions'][0].id}/messaging-secrets").json()["cleared"] == 1
    assert admin(env).post(f"/api/messaging/messages/{draft['id']}/send", json=dict(answer="nyeri")).status_code == 409  # Must set a new one.


def test_drafts_validate_placeholders_and_audience(env, school):
    bad = admin(env).post("/api/messaging/messages", json=dict(kind="ANNOUNCEMENT", title="Oops", template="Balance {balance}"))
    assert bad.status_code == 422
    assert admin(env).post("/api/messaging/messages", json=dict(kind="FEES", title="Fees", template="Hi")).status_code == 422
    assert env["as_user"](env["teacher"]).post("/api/messaging/messages", json=dict(kind="ANNOUNCEMENT", title="Mine", template="Hello")).status_code == 403


def test_fee_reminder_preview_allowance_send_and_delivery(env, school):
    set_secret(env)
    template = "Dear parent, {student} has a fee balance of {balance} for {term}. {school}"
    draft = admin(env).post("/api/messaging/messages", json=dict(kind="FEES", title="Fee balances", template=template,
                                                                  audience=dict(period_id=str(school["term"].id)))).json()
    preview = admin(env).get(f"/api/messaging/messages/{draft['id']}/preview").json()
    # Only the student with a balance; only the main contact; SMS plus an email copy.
    assert (preview["sms"], preview["email"], preview["parts"], preview["fits"]) == (1, 1, 1, False)
    assert preview["samples"][0]["body"] == "Dear parent, pupil Test has a fee balance of KES 12,500 for Term 3. School 0"
    url = f"/api/messaging/messages/{draft['id']}/send"
    assert admin(env).post(url, json=dict(answer="NYERI")).status_code == 409  # No allowance yet.
    owner_user = platform(env)
    owner = env["as_user"](owner_user)
    assert owner.put(f"/api/platform/institutions/{env['institutions'][0].id}/sms-allowance", json=dict(monthly_parts=10)).status_code == 200
    sent = admin(env).post(url, json=dict(answer="nyeri"))
    assert sent.status_code == 200, sent.text
    db = env["db"]; db.expire_all()
    rows = {d.channel: d for d in db.query(MessageDelivery).all()}
    assert rows["SMS"].status == "SENT" and rows["SMS"].address == "+254712345678" and rows["EMAIL"].status == "SENT"
    assert school["emails"][0]["to"] == "lucy@example.test"
    assert db.query(GuardianMessage).one().status == "SENT"
    assert admin(env).post(url, json=dict(answer="nyeri")).status_code == 409  # Never sent twice.
    # Delivery report from Africa's Talking.
    report = env["client"].post(f"/api/messaging/at/{'d' * 40}/delivery", content=f"id={rows['SMS'].provider_id}&status=Success&phoneNumber=%2B254712345678",
                                headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert report.status_code == 200
    assert env["client"].post("/api/messaging/at/wrong/delivery", content="id=x").status_code == 404
    db.expire_all()
    assert db.get(MessageDelivery, rows["SMS"].id).status == "DELIVERED"
    usage = env["as_user"](owner_user).get("/api/platform/messaging/usage").json()
    mine = next(r for r in usage["rows"] if r["name"] == "School 0")
    assert (mine["allowance"], mine["sms_parts"], mine["emails"]) == (10, 1, 1)


def test_school_notice_reaches_each_guardian_once(env, school):
    set_secret(env)
    env["as_user"](platform(env)).put(f"/api/platform/institutions/{env['institutions'][0].id}/sms-allowance", json=dict(monthly_parts=100))
    draft = admin(env).post("/api/messaging/messages", json=dict(kind="EMERGENCY", title="Closure", template="{school} is closed today due to flooding.",
                                                                  audience=dict(scope="SCHOOL", all_guardians=True))).json()
    preview = admin(env).get(f"/api/messaging/messages/{draft['id']}/preview").json()
    # Lucy has two children but gets one SMS; John (not main contact) is included because all guardians were chosen.
    assert preview["sms"] == 2 and preview["email"] == 1
    assert admin(env).post(f"/api/messaging/messages/{draft['id']}/send", json=dict(answer="nyeri")).status_code == 200
    assert len(school["sent"]) == 1 and sorted(school["sent"][0][0]) == ["+254712345678", "+254722000111"]  # One batch for the same text.


def test_failed_sms_can_be_retried(env, school, monkeypatch):
    set_secret(env)
    env["as_user"](platform(env)).put(f"/api/platform/institutions/{env['institutions'][0].id}/sms-allowance", json=dict(monthly_parts=100))
    monkeypatch.setattr(sms, "send", lambda numbers, message: {n: dict(accepted=False, message_id=None, cost=None, status="InvalidPhoneNumber") for n in numbers})
    draft = admin(env).post("/api/messaging/messages", json=dict(kind="ANNOUNCEMENT", title="Trip", template="Trip forms due Monday.")).json()
    admin(env).post(f"/api/messaging/messages/{draft['id']}/send", json=dict(answer="nyeri"))
    detail = admin(env).get(f"/api/messaging/messages/{draft['id']}").json()
    assert detail["counts"]["SMS"] == {"FAILED": 1}
    assert next(d for d in detail["deliveries"] if d["channel"] == "SMS")["error"] == "InvalidPhoneNumber"
    monkeypatch.setattr(sms, "send", lambda numbers, message: {n: dict(accepted=True, message_id="ok-" + n, cost=None, status="Success") for n in numbers})
    assert admin(env).post(f"/api/messaging/messages/{draft['id']}/retry", json=dict(answer="nyeri")).json()["queued"] >= 1
    assert admin(env).get(f"/api/messaging/messages/{draft['id']}").json()["counts"]["SMS"] == {"SENT": 1}
