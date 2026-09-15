"""
One-off script: creates the first Platform Super Admin account.

Run once, manually (interactive):
    python seed_super_admin.py

Run non-interactively via environment variables (e.g. on Render):
    SUPER_ADMIN_EMAIL=admin@example.com \
    SUPER_ADMIN_PASSWORD=supersecure123 \
    SUPER_ADMIN_USERNAME=superadmin \
    SUPER_ADMIN_FIRST_NAME=Super \
    SUPER_ADMIN_LAST_NAME=Admin \
    python seed_super_admin.py

Why this exists: our account-creation model has no self-registration
anywhere — every account is created by a higher-level role. But the very
first Super Admin has no one above them to do the creating. This script is
the one deliberate exception, run directly against the database rather than
through the API, specifically because there is no API endpoint that should
ever be able to create a Platform Admin (that would be a serious privilege-
escalation hole if it existed).
"""

import getpass
import os
import re

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole, UserStatus

EMAIL_PATTERN = re.compile(r"^[^\@\s]+@[^\@\s]+\.[^\@\s]+$")


def _prompt(label: str, env_var: str, secret: bool = False) -> str:
    """Return env var value if set, otherwise prompt the user."""
    value = os.environ.get(env_var, "").strip()
    if value:
        masked = "****" if secret else value
        print(f"{label}: {masked}  (from env {env_var})")
        return value
    if secret:
        return getpass.getpass(f"{label}: ")
    return input(f"{label}: ").strip()


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == UserRole.PLATFORM_ADMIN).first()
        if existing:
            print(f"A Platform Admin already exists: {existing.username}. Aborting.")
            return

        print("Creating the first Platform Super Admin account.")
        first_name = _prompt("First name", "SUPER_ADMIN_FIRST_NAME") or "Super"
        last_name  = _prompt("Last name",  "SUPER_ADMIN_LAST_NAME")  or "Admin"
        username   = _prompt("Username",   "SUPER_ADMIN_USERNAME")
        email      = _prompt("Email",      "SUPER_ADMIN_EMAIL")
        password   = _prompt("Password",   "SUPER_ADMIN_PASSWORD", secret=True)

        if not username:
            print("Username is required. Aborting.")
            return
        if not email or not EMAIL_PATTERN.match(email):
            print("A valid email is required. Aborting.")
            return
        if not password or len(password) < 12:
            print("Password must be at least 12 characters. Aborting.")
            return

        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            print(f"A user with email '{email}' already exists. Aborting.")
            return

        admin = User(
            institution_id=None,
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.PLATFORM_ADMIN,
            status=UserStatus.ACTIVE,
            must_change_password=False,
        )
        db.add(admin)
        db.commit()
        print(f"Platform Super Admin '{username}' created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()