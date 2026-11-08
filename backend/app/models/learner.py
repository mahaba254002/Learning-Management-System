"""Learner portal: recently opened courses and messages that teachers and admins send to students."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CourseVisit(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """When a student last opened a course. One row per student and course."""
    __tablename__ = 'course_visits'
    __table_args__ = (
        ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'subject_id'], ['teaching_subjects.institution_id', 'teaching_subjects.id'], ondelete='CASCADE'),
        UniqueConstraint('user_id', 'subject_id', name='uq_course_visits_user_subject'),
        Index('ix_course_visits_recent', 'institution_id', 'user_id', 'visited_at'),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    subject_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StudentMessage(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A message from a teacher or admin to one student or a whole class. Students can read but not reply."""
    __tablename__ = 'student_messages'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id'),
        ForeignKeyConstraint(['institution_id', 'sender_id'], ['users.institution_id', 'users.id']),
        ForeignKeyConstraint(['institution_id', 'class_id'], ['academic_classes.institution_id', 'academic_classes.id']),
        CheckConstraint("audience IN ('STUDENT', 'CLASS')", name='ck_student_messages_audience'),
        Index('ix_student_messages_sent', 'institution_id', 'sender_id', 'created_at'),
        Index('ix_student_messages_recent', 'institution_id', 'created_at'),
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    audience: Mapped[str] = mapped_column(String(8))
    class_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)


class StudentMessageRecipient(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'student_message_recipients'
    __table_args__ = (
        ForeignKeyConstraint(['institution_id', 'message_id'], ['student_messages.institution_id', 'student_messages.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id'], ondelete='CASCADE'),
        UniqueConstraint('message_id', 'user_id', name='uq_student_message_recipient'),
        Index('ix_student_message_inbox', 'institution_id', 'user_id', 'created_at'),
    )
    message_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
