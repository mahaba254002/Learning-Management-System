"""E-learning: uploaded files, online quizzes, registration windows and in-app notifications."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

FILE_PURPOSES = ('MATERIAL', 'PAPER', 'SUBMISSION')
QUESTION_KINDS = ('SINGLE', 'MULTIPLE', 'TRUE_FALSE')


class StoredFile(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """One uploaded file. The bytes live in object storage under storage_key."""
    __tablename__ = 'stored_files'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id'),
        UniqueConstraint('storage_key'),
        ForeignKeyConstraint(['institution_id', 'uploaded_by'], ['users.institution_id', 'users.id']),
        ForeignKeyConstraint(['institution_id', 'subject_id'], ['teaching_subjects.institution_id', 'teaching_subjects.id']),
        ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
        CheckConstraint("purpose IN ('MATERIAL', 'PAPER', 'SUBMISSION')", name='ck_stored_files_purpose'),
        CheckConstraint('size_bytes > 0 AND size_bytes <= 10485760', name='ck_stored_files_size'),
        CheckConstraint("(purpose = 'SUBMISSION') = (student_id IS NOT NULL)", name='ck_stored_files_student'),
        Index('ix_stored_files_usage', 'institution_id', 'deleted_at'),
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    purpose: Mapped[str] = mapped_column(String(12))
    subject_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    filename: Mapped[str] = mapped_column(String(160))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(200))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuizSettings(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """Rules for an online quiz. The quiz itself is a Coursework row with delivery QUIZ."""
    __tablename__ = 'quiz_settings'
    __table_args__ = (
        UniqueConstraint('institution_id', 'coursework_id', name='uq_quiz_settings_quiz'),
        ForeignKeyConstraint(['institution_id', 'coursework_id'], ['coursework.institution_id', 'coursework.id'], ondelete='CASCADE'),
        CheckConstraint('time_limit_minutes IS NULL OR (time_limit_minutes >= 1 AND time_limit_minutes <= 600)', name='ck_quiz_settings_time'),
        CheckConstraint('attempts_allowed >= 1 AND attempts_allowed <= 10', name='ck_quiz_settings_attempts'),
    )
    coursework_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts_allowed: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    no_going_back: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    shuffle_options: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    hide_results_until_close: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    log_tab_switches: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')


class QuizQuestion(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'quiz_questions'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id'),
        ForeignKeyConstraint(['institution_id', 'coursework_id'], ['coursework.institution_id', 'coursework.id'], ondelete='CASCADE'),
        CheckConstraint("kind IN ('SINGLE', 'MULTIPLE', 'TRUE_FALSE')", name='ck_quiz_questions_kind'),
        CheckConstraint('points > 0 AND points <= 1000', name='ck_quiz_questions_points'),
        CheckConstraint('time_limit_seconds IS NULL OR (time_limit_seconds >= 10 AND time_limit_seconds <= 3600)', name='ck_quiz_questions_time'),
    )
    coursework_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(12))
    prompt: Mapped[str] = mapped_column(Text)
    # [{"id": "a", "text": "..."}]; correct is a list of option ids.
    options: Mapped[list] = mapped_column(JSONType)
    correct: Mapped[list] = mapped_column(JSONType)
    points: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)


class QuizAttempt(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'quiz_attempts'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id'),
        UniqueConstraint('institution_id', 'coursework_id', 'student_id', 'number'),
        ForeignKeyConstraint(['institution_id', 'coursework_id'], ['coursework.institution_id', 'coursework.id']),
        ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
        CheckConstraint("status IN ('IN_PROGRESS', 'SUBMITTED')", name='ck_quiz_attempts_status'),
        CheckConstraint('number >= 1', name='ck_quiz_attempts_number'),
        # One open attempt per student per quiz.
        Index('uq_quiz_attempts_open', 'institution_id', 'coursework_id', 'student_id', unique=True,
              postgresql_where=text("status = 'IN_PROGRESS'"), sqlite_where=text("status = 'IN_PROGRESS'")),
    )
    coursework_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default='IN_PROGRESS')
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_submitted: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    # [{"q": question id, "o": [option ids in display order]}]
    plan: Mapped[list] = mapped_column(JSONType)
    sequential: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    current_index: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    current_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    max_score: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    tab_switches: Mapped[int] = mapped_column(Integer, default=0, server_default='0')


class QuizAnswer(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'quiz_answers'
    __table_args__ = (
        UniqueConstraint('institution_id', 'attempt_id', 'question_id'),
        ForeignKeyConstraint(['institution_id', 'attempt_id'], ['quiz_attempts.institution_id', 'quiz_attempts.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'question_id'], ['quiz_questions.institution_id', 'quiz_questions.id']),
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    selected: Mapped[list] = mapped_column(JSONType)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuizExtraAttempt(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """One more attempt for one student, granted by a teacher with a reason (e.g. a power cut)."""
    __tablename__ = 'quiz_extra_attempts'
    __table_args__ = (
        ForeignKeyConstraint(['institution_id', 'coursework_id'], ['coursework.institution_id', 'coursework.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
        ForeignKeyConstraint(['institution_id', 'granted_by'], ['users.institution_id', 'users.id']),
    )
    coursework_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    granted_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(String(300))


class RegistrationWindow(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A period when students choose optional units themselves, within limits."""
    __tablename__ = 'registration_windows'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id'),
        ForeignKeyConstraint(['institution_id', 'period_id'], ['academic_periods.institution_id', 'academic_periods.id']),
        CheckConstraint('closes_at > opens_at', name='ck_registration_windows_dates'),
        CheckConstraint('min_units >= 0 AND max_units >= min_units AND max_units <= 50', name='ck_registration_windows_units'),
        CheckConstraint('min_credits IS NULL OR max_credits IS NULL OR max_credits >= min_credits', name='ck_registration_windows_credits'),
    )
    title: Mapped[str] = mapped_column(String(120))
    period_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    min_units: Mapped[int] = mapped_column(Integer, default=0)
    max_units: Mapped[int] = mapped_column(Integer)
    min_credits: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    max_credits: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    # Empty means every class.
    class_ids: Mapped[list] = mapped_column(JSONType, default=list)


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'notifications'
    __table_args__ = (
        ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id'], ondelete='CASCADE'),
        # The same event never notifies one person twice.
        UniqueConstraint('user_id', 'ref', name='uq_notifications_user_ref'),
        Index('ix_notifications_inbox', 'user_id', 'created_at'),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    ref: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(500), default='')
    link: Mapped[str] = mapped_column(String(300), default='')
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
