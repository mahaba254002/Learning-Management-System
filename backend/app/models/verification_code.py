import enum
import uuid

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class VerificationPurpose(str, enum.Enum):
    CREATE_INSTITUTION = "CREATE_INSTITUTION"
    DELETE_INSTITUTION = "DELETE_INSTITUTION"
    PASSWORD_RESET = "PASSWORD_RESET"


class VerificationCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "verification_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    purpose: Mapped[VerificationPurpose] = mapped_column(
        Enum(VerificationPurpose, name="verification_purpose"), nullable=False
    )

    # Never store the raw 6-digit code — same principle as passwords.
    # We hash it with the same argon2 helper we already use for passwords.
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # The pending action's data (e.g. the institution fields to create, or
    # {"institution_id": "..."} for a delete), so the admin doesn't have to
    # resubmit the whole form after entering the code.
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    expires_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)

    attempt_count: Mapped[int] = mapped_column(default=0)