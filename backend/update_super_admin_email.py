"""One-off script: update the Platform Super Admin email."""

from app.db.session import SessionLocal
from app.models.user import User, UserRole

NEW_EMAIL = "mahaba955+superadmin@gmail.com"

def main() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.PLATFORM_ADMIN).first()
        if not admin:
            print("No Platform Admin found.")
            return
        old_email = admin.email
        admin.email = NEW_EMAIL
        db.commit()
        print(f"Email updated: '{old_email}' → '{NEW_EMAIL}' for '{admin.username}'.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
