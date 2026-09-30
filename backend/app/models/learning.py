import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CourseMaterial(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "course_materials"
    __table_args__ = (
        UniqueConstraint("institution_id", "id"),
        ForeignKeyConstraint(["institution_id", "subject_id"], ["teaching_subjects.institution_id", "teaching_subjects.id"]),
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)


class Submission(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint("institution_id", "id"),
        UniqueConstraint("institution_id", "coursework_id", "student_id"),
        ForeignKeyConstraint(["institution_id", "coursework_id"], ["coursework.institution_id", "coursework.id"]),
        ForeignKeyConstraint(["institution_id", "student_id"], ["students.institution_id", "students.id"]),
        CheckConstraint("status IN ('DRAFT', 'SUBMITTED')"),
        CheckConstraint("version > 0"),
    )
    coursework_id: Mapped[uuid.UUID] = mapped_column(index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    answer: Mapped[str] = mapped_column(Text, default="")
    link_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="DRAFT")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
