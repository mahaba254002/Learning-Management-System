import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY"


class EmploymentType(str, enum.Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    VISITING = "VISITING"


class TeacherStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ON_LEAVE = "ON_LEAVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


class Teacher(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "teachers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )

    gender: Mapped[Gender] = mapped_column(Enum(Gender, name="gender"), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    qualification: Mapped[str] = mapped_column(String(255), nullable=False)
    specialization: Mapped[str | None] = mapped_column(String(255), nullable=True)

    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType, name="employment_type"), nullable=False
    )

    status: Mapped[TeacherStatus] = mapped_column(
        Enum(TeacherStatus, name="teacher_status"), nullable=False, default=TeacherStatus.ACTIVE
    )

    invited_from: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invitations.id"), nullable=True
    )