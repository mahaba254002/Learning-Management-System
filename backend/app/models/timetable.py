"""Timetables entered by the institution administrator, one per term or semester.

The administrator sets the bell schedule (lesson periods and breaks), marks when
teachers are unavailable, then places each lesson. Nothing is generated or
imported. Teachers and students see a term's timetable once it is published."""
import uuid
from datetime import date, datetime, time

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKeyConstraint, Index, SmallInteger, String,
                        Time, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TimetableTerm(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """Settings for one term's timetable: teaching days and whether it is published."""
    __tablename__ = 'timetable_terms'
    __table_args__ = (
        UniqueConstraint('institution_id', 'period_id', name='uq_timetable_terms_period'),
        ForeignKeyConstraint(['institution_id', 'period_id'], ['academic_periods.institution_id', 'academic_periods.id'], ondelete='CASCADE'),
    )
    period_id: Mapped[uuid.UUID] = mapped_column()
    # ISO weekdays: 1 Monday ... 7 Sunday.
    weekdays: Mapped[list] = mapped_column(JSONType, default=lambda: [1, 2, 3, 4, 5])
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TimetableSlot(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A lesson period or break in the bell schedule, e.g. Lesson 1, 08:00-08:40."""
    __tablename__ = 'timetable_slots'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id', name='uq_timetable_slots_tenant_id'),
        ForeignKeyConstraint(['institution_id', 'period_id'], ['academic_periods.institution_id', 'academic_periods.id'], ondelete='CASCADE'),
        CheckConstraint('end_time > start_time', name='ck_timetable_slots_times'),
        Index('ix_timetable_slots_period', 'institution_id', 'period_id', 'start_time'),
    )
    period_id: Mapped[uuid.UUID] = mapped_column()
    label: Mapped[str] = mapped_column(String(40))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    is_break: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    # Days this period runs on; empty means every teaching day of the term.
    weekdays: Mapped[list] = mapped_column(JSONType, default=list)


class TimetableEntry(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """One weekly lesson: a subject offering, its teacher, a day and a lesson period."""
    __tablename__ = 'timetable_entries'
    __table_args__ = (
        Index('ix_timetable_entries_subject', 'institution_id', 'subject_id'),
        UniqueConstraint('institution_id', 'id', name='uq_timetable_entries_tenant_id'),
        UniqueConstraint('institution_id', 'slot_id', 'weekday', 'subject_id', name='uq_timetable_entries_lesson'),
        ForeignKeyConstraint(['institution_id', 'period_id'], ['academic_periods.institution_id', 'academic_periods.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'slot_id'], ['timetable_slots.institution_id', 'timetable_slots.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'subject_id'], ['teaching_subjects.institution_id', 'teaching_subjects.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'class_id'], ['academic_classes.institution_id', 'academic_classes.id']),
        ForeignKeyConstraint(['institution_id', 'teacher_id'], ['users.institution_id', 'users.id']),
        CheckConstraint('weekday BETWEEN 1 AND 7', name='ck_timetable_entries_weekday'),
        Index('ix_timetable_entries_teacher', 'institution_id', 'period_id', 'teacher_id', 'weekday'),
        Index('ix_timetable_entries_class', 'institution_id', 'period_id', 'class_id', 'weekday'),
    )
    period_id: Mapped[uuid.UUID] = mapped_column()
    slot_id: Mapped[uuid.UUID] = mapped_column()
    weekday: Mapped[int] = mapped_column(SmallInteger)
    subject_id: Mapped[uuid.UUID] = mapped_column()
    class_id: Mapped[uuid.UUID] = mapped_column()
    teacher_id: Mapped[uuid.UUID] = mapped_column()
    # Set when the administrator saved this lesson despite a clash.
    override_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)


class TeacherUnavailability(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A weekly time a teacher cannot teach this term, e.g. part-time days."""
    __tablename__ = 'teacher_unavailability'
    __table_args__ = (
        ForeignKeyConstraint(['institution_id', 'period_id'], ['academic_periods.institution_id', 'academic_periods.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'teacher_id'], ['users.institution_id', 'users.id']),
        CheckConstraint('weekday BETWEEN 1 AND 7', name='ck_teacher_unavailability_weekday'),
        CheckConstraint('end_time > start_time', name='ck_teacher_unavailability_times'),
        Index('ix_teacher_unavailability_teacher', 'institution_id', 'period_id', 'teacher_id', 'weekday'),
    )
    period_id: Mapped[uuid.UUID] = mapped_column()
    teacher_id: Mapped[uuid.UUID] = mapped_column()
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    reason: Mapped[str] = mapped_column(String(200), default='', server_default='')


class LessonChange(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A one-day change to a weekly lesson: cancelled, moved or taught by a substitute."""
    __tablename__ = 'lesson_changes'
    __table_args__ = (
        UniqueConstraint('institution_id', 'entry_id', 'lesson_date', name='uq_lesson_changes_once'),
        ForeignKeyConstraint(['institution_id', 'entry_id'], ['timetable_entries.institution_id', 'timetable_entries.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'new_slot_id'], ['timetable_slots.institution_id', 'timetable_slots.id']),
        ForeignKeyConstraint(['institution_id', 'substitute_id'], ['users.institution_id', 'users.id']),
        ForeignKeyConstraint(['institution_id', 'created_by'], ['users.institution_id', 'users.id']),
        CheckConstraint("kind IN ('CANCELLED', 'MOVED', 'SUBSTITUTE')", name='ck_lesson_changes_kind'),
        CheckConstraint("(kind = 'SUBSTITUTE') = (substitute_id IS NOT NULL)", name='ck_lesson_changes_substitute'),
        CheckConstraint("(kind = 'MOVED') = (new_date IS NOT NULL AND new_slot_id IS NOT NULL)", name='ck_lesson_changes_move'),
        Index('ix_lesson_changes_dates', 'institution_id', 'lesson_date'),
        Index('ix_lesson_changes_new_date', 'institution_id', 'new_date'),
    )
    entry_id: Mapped[uuid.UUID] = mapped_column()
    lesson_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(10))
    substitute_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    new_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    new_slot_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    note: Mapped[str] = mapped_column(String(300), default='', server_default='')
    override_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column()
