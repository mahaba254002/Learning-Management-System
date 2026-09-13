import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EmailFailure(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "email_failures"

    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)

    # What kind of email this was (e.g. "PASSWORD_RESET", "TEACHER_INVITE",
    # "VERIFICATION_CODE") — lets a future Audit Logs page filter/group.
    email_type: Mapped[str] = mapped_column(String(100), nullable=False)

    error_message: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Free-form context (e.g. institution_id, user_id involved) for
    # debugging — not strictly typed since failure context varies by flow.
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    resolved: Mapped[bool] = mapped_column(default=False)