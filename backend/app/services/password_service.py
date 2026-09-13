"""Generates a secure, random temporary password for admin-created accounts."""

import secrets
import string


def generate_temporary_password(length: int = 16) -> str:
    # Mix of letters, digits, and a couple of symbols — strong by
    # construction since it's random, not memorable/guessable like a
    # human-chosen "temporary password" often is.
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))