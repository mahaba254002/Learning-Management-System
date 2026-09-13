import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class UUIDPrimaryKeyMixin:
    """Every table uses a UUID primary key instead of an auto-increment
    integer. Reason: sequential integer IDs are guessable (?id=124 -> try
    125), which is a mild info-leak risk, and UUIDs let us generate a new
    row's ID in Python before it's even saved to the database."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TenantMixin:
    """Adds institution_id to a model. This is the column our tenant-
    isolation repository layer filters every query by."""

    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False, index=True
    )