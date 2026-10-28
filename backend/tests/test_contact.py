import pytest
from test_teaching import env

from app.api.routes import contact
from app.core import rate_limit as limiter
from app.services.email_service import EmailSendError


@pytest.fixture(autouse=True)
def contact_services(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, "incr", lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, "expire", lambda *args: True)
    monkeypatch.setattr(contact.settings, "PRODUCT_ENQUIRY_EMAIL", "enquiries@example.test")


def enquiry(**changes):
    return dict(name="School visitor", email="visitor@example.test", institution="School One",
                sector="College", message="Please tell me more about the product.", **changes)


def test_public_enquiry_delivers_to_configured_inbox_and_escapes_text(env, monkeypatch):
    deliveries = []
    monkeypatch.setattr(contact, "send_email", lambda **values: deliveries.append(values))
    body = enquiry()
    body["message"] = '<script>alert("x")</script>\nPlease send product details.'
    result = env["client"].post("/api/contact/enquiries", json=body)
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert deliveries[0]["to"] == "enquiries@example.test"
    assert deliveries[0]["subject"] == "Skynet enquiry: College"
    assert "<script>" not in deliveries[0]["html_body"]
    assert "&lt;script&gt;" in deliveries[0]["html_body"]
    assert "visitor@example.test" in deliveries[0]["html_body"]


@pytest.mark.parametrize("change", [{"email": "invalid"}, {"sector": "Unknown"}, {"message": " "}, {"message": "x" * 4001}, {"to": "attacker@example.test"}])
def test_invalid_and_recipient_override_rejected(env, monkeypatch, change):
    deliveries = []
    monkeypatch.setattr(contact, "send_email", lambda **values: deliveries.append(values))
    assert env["client"].post("/api/contact/enquiries", json={**enquiry(), **change}).status_code == 422
    assert not deliveries


def test_missing_configuration_or_delivery_failure_never_reports_success(env, monkeypatch):
    monkeypatch.setattr(contact.settings, "PRODUCT_ENQUIRY_EMAIL", "")
    assert env["client"].post("/api/contact/enquiries", json=enquiry()).status_code == 503
    monkeypatch.setattr(contact.settings, "PRODUCT_ENQUIRY_EMAIL", "enquiries@example.test")
    def fail(**values):
        raise EmailSendError("test failure")
    monkeypatch.setattr(contact, "send_email", fail)
    assert env["client"].post("/api/contact/enquiries", json=enquiry()).status_code == 503


def test_public_enquiry_is_rate_limited(env, monkeypatch):
    monkeypatch.setattr(limiter.redis_client, "incr", lambda key: 100000)
    assert env["client"].post("/api/contact/enquiries", json=enquiry()).status_code == 429
