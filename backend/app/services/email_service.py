"""
Central email-sending service. Every place in the app that needs to send
an email calls send_email() — this is the ONE place that knows about
Resend specifically. If we ever switch providers, only this file changes.

Design: sending is NOT best-effort. If it fails, we raise EmailSendError
and the caller is expected to fail its own request and roll back whatever
it was about to commit — we do not want to tell a user "check your email"
when no email actually went out.
"""

import logging
from importlib import import_module
from typing import Any

from app.core.config import settings

logger = logging.getLogger("app.email")

try:
    resend: Any = import_module("resend")
except ModuleNotFoundError:
    resend = None

if resend is not None:
    resend.api_key = settings.RESEND_API_KEY


class EmailSendError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def send_email(*, to: str, subject: str, html_body: str) -> None:
    if not settings.RESEND_API_KEY or resend is None:
        # Fail loudly in any environment where email is expected to work.
        # This should only ever be hit if .env is misconfigured.
        raise EmailSendError(
            "Email service is not configured (missing RESEND_API_KEY or resend package)"
        )

    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM_ADDRESS,
            "to": [to],
            "subject": subject,
            "html": html_body,
        })
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        raise EmailSendError(str(exc)) from exc