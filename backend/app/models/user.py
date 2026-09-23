import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    INSTITUTION_ADMIN = "INSTITUTION_ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INVITED = "INVITED"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Nullable ONLY for PLATFORM_ADMIN — every other role must belong to an
    # institution. Enforced in application code (service layer, next steps),
    # not a DB constraint, so we can give a clear error message instead of
    # a raw database error.
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True, index=True
    )

    # Auto-generated as "{first_name}.{last_name}.{institution.code}",
    # disambiguated with a trailing number on collision within the
    # institution. Globally unique across the whole platform by construction.
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Optional. Used only for password-reset delivery and notifications —
    # never for login.
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)

    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), nullable=False, default=UserStatus.ACTIVE
    )

    # True until the user completes their first login and sets their own
    # password. Checked by the login flow to force a password-change step.
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Stamped every time this user's password changes (self-service change,
    # self-service reset, or admin-assisted reset). get_current_context
    # rejects any token issued before this timestamp, so an old session
    # cannot outlive a password reset — this matters most for the
    # admin-assisted student reset path, where the reset may be a response
    # to a compromised account.
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )