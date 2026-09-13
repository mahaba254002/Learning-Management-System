"""
Password policy for user-chosen passwords (used when a user sets their own
password after being forced to change a temporary one, and later for
self-service password changes/resets).

Rules: minimum 8 characters, must contain at least one uppercase letter,
one lowercase letter, one digit, and one symbol.
"""

import re


class PasswordPolicyError(Exception):
    """Raised with a human-readable message describing which rule failed."""


MIN_LENGTH = 8
SYMBOL_PATTERN = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]")


def validate_password_policy(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise PasswordPolicyError(f"Password must be at least {MIN_LENGTH} characters long")

    if not any(c.isupper() for c in password):
        raise PasswordPolicyError("Password must contain at least one uppercase letter")

    if not any(c.islower() for c in password):
        raise PasswordPolicyError("Password must contain at least one lowercase letter")

    if not any(c.isdigit() for c in password):
        raise PasswordPolicyError("Password must contain at least one digit")

    if not SYMBOL_PATTERN.search(password):
        raise PasswordPolicyError("Password must contain at least one symbol (e.g. !@#$%^&*)")