"""
Teacher (and future role) invitation flow.

Lifecycle: SENT -> SUBMITTED -> APPROVED or REJECTED, with EXPIRED as a
fallback state once expires_at passes without submission/action. The
invitation holds the teacher's self-reported data in `submitted_data`
until an Institution Admin approves it, at which point a real users +
teachers row is created from that data — the invitation itself is never
converted into a user directly, it's just the holding pen.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class InvitationRole(str, enum.Enum):
    TEACHER = "TEACHER"


class InvitationStatus(str, enum.Enum):
    SENT = "SENT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class Invitation(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "invitations"

    invited_role: Mapped[InvitationRole] = mapped_column(
        Enum(InvitationRole, name="invitation_role"), nullable=False
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # The secret token embedded in the invite link. Random, unguessable,
    # unique — this IS the authentication for the public submit endpoint,
    # same trust model as a password-reset link.
    invite_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    status: Mapped[InvitationStatus] = mapped_column(
        Enum(InvitationStatus, name="invitation_status"),
        nullable=False,
        default=InvitationStatus.SENT,
    )

    # Populated once the invited person fills out the form. Null until then.
    submitted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    invited_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Set to the newly created user's id once approved — lets us trace an
    # account back to the invitation that originated it.
    created_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)