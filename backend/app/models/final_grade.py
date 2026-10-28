import uuid
from sqlalchemy import Boolean, ForeignKeyConstraint, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class FinalGrade(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__='final_grades'
    __table_args__=(UniqueConstraint('institution_id','subject_id','student_id','scope'),
        ForeignKeyConstraint(['institution_id','subject_id'],['teaching_subjects.institution_id','teaching_subjects.id']),
        ForeignKeyConstraint(['institution_id','student_id'],['students.institution_id','students.id']))
    subject_id: Mapped[uuid.UUID] = mapped_column(index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    scope: Mapped[str] = mapped_column(String(36))
    source_digest: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)
    released: Mapped[bool] = mapped_column(Boolean,default=False)
