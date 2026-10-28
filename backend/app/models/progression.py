import uuid
from sqlalchemy import CheckConstraint,ForeignKeyConstraint,JSON,String,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base,TenantMixin,TimestampMixin,UUIDPrimaryKeyMixin


class Prerequisite(UUIDPrimaryKeyMixin,TimestampMixin,TenantMixin,Base):
    __tablename__='course_prerequisites'
    __table_args__=(UniqueConstraint('institution_id','course_id','required_id'),
        ForeignKeyConstraint(['institution_id','course_id'],['academic_catalogue.institution_id','academic_catalogue.id']),
        ForeignKeyConstraint(['institution_id','required_id'],['academic_catalogue.institution_id','academic_catalogue.id']),
        CheckConstraint('course_id != required_id'))
    course_id:Mapped[uuid.UUID]=mapped_column(index=True)
    required_id:Mapped[uuid.UUID]=mapped_column(index=True)
    minimum_percentage:Mapped[str|None]=mapped_column(String(12),nullable=True)


class ProgressionDecision(UUIDPrimaryKeyMixin,TimestampMixin,TenantMixin,Base):
    __tablename__='progression_decisions'
    __table_args__=(UniqueConstraint('institution_id','source_class_id','student_id'),
        ForeignKeyConstraint(['institution_id','source_class_id'],['academic_classes.institution_id','academic_classes.id']),
        ForeignKeyConstraint(['institution_id','target_class_id'],['academic_classes.institution_id','academic_classes.id']),
        ForeignKeyConstraint(['institution_id','student_id'],['students.institution_id','students.id']),
        CheckConstraint("decision IN ('ADVANCE','REPEAT','COMPLETE')"))
    source_class_id:Mapped[uuid.UUID]=mapped_column(index=True)
    target_class_id:Mapped[uuid.UUID|None]=mapped_column(nullable=True)
    student_id:Mapped[uuid.UUID]=mapped_column(index=True)
    decision:Mapped[str]=mapped_column(String(10))
    snapshot:Mapped[dict]=mapped_column(JSON)
