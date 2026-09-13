"""
One-off script: creates the first Platform Super Admin account.

Run once, manually:
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

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole, UserStatus


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == UserRole.PLATFORM_ADMIN).first()
        if existing:
            print(f"A Platform Admin already exists: {existing.username}. Aborting.")
            return

        print("Creating the first Platform Super Admin account.")
        first_name = input("First name: ").strip()
        last_name = input("Last name: ").strip()
        username = input("Username (e.g. superadmin): ").strip()
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")

        if password != confirm:
            print("Passwords do not match. Aborting.")
            return
        if len(password) < 12:
            print("Password must be at least 12 characters. Aborting.")
            return

        admin = User(
            institution_id=None,
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=None,
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