"""One-off script: reset the Platform Super Admin password."""

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole

NEW_PASSWORD = "Mahaba@Super2025!"

def main() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.PLATFORM_ADMIN).first()
        if not admin:
            print("No Platform Admin found.")
            return
        admin.password_hash = hash_password(NEW_PASSWORD)
        admin.must_change_password = False
        db.commit()
        print(f"Password reset successfully for '{admin.username}' ({admin.email}).")
    finally:
        db.close()

if __name__ == "__main__":
    main()
