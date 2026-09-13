import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InstitutionType(str, enum.Enum):
    UNIVERSITY = "UNIVERSITY"
    COLLEGE = "COLLEGE"
    HIGH_SCHOOL = "HIGH_SCHOOL"
    PRIMARY_SCHOOL = "PRIMARY_SCHOOL"
    TRAINING_INSTITUTION = "TRAINING_INSTITUTION"
    OTHER = "OTHER"


class InstitutionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"  # soft-deleted: data preserved, all access locked out


class Institution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institutions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    type: Mapped[InstitutionType] = mapped_column(
        Enum(InstitutionType, name="institution_type"), nullable=False
    )

    country: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    official_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[InstitutionStatus] = mapped_column(
        Enum(InstitutionStatus, name="institution_status"),
        nullable=False,
        default=InstitutionStatus.ACTIVE,
    )

    # Audit trail for the archive action — who did it, and when. Nullable
    # because most institutions are never archived.
    archived_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )