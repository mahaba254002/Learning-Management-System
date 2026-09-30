import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ClassInput(Input):
    name: Name
    academic_year: str = Field(min_length=1, max_length=30)
    supervisor_id: uuid.UUID | None = None


class SubjectInput(Input):
    name: Name
    teacher_id: uuid.UUID


class StudentInput(Input):
    first_name: Name
    last_name: Name
    admission_number: str = Field(min_length=1, max_length=60)
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    phone: str | None = Field(default=None, max_length=50)


class StudentEdit(Input):
    first_name: Name
    last_name: Name
    phone: str | None = Field(default=None, max_length=50)


class EnrollInput(Input):
    admission_number: str = Field(min_length=1, max_length=60)


class CourseworkInput(Input):
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=20000)
    kind: Literal["ASSIGNMENT", "COURSEWORK", "EXAM"] = "ASSIGNMENT"
    due_at: AwareDatetime | None = None
    max_score: Decimal = Field(gt=0, le=10000, max_digits=8, decimal_places=2)
    published: bool = False
    allow_late_submissions: bool = True


class ScoreInput(Input):
    student_id: uuid.UUID
    score: Decimal = Field(ge=0, le=10000, max_digits=8, decimal_places=2)
    feedback: str = Field(default="", max_length=5000)


class ScoresInput(Input):
    entries: list[ScoreInput] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_students(self):
        if len({e.student_id for e in self.entries}) != len(self.entries):
            raise ValueError("A student may appear only once")
        return self


class AttendanceInput(Input):
    student_id: uuid.UUID
    status: Literal["PRESENT", "ABSENT", "LATE", "EXCUSED"]
    note: str = Field(default="", max_length=500)


class RegisterInput(Input):
    day: date
    subject_id: uuid.UUID | None = None
    entries: list[AttendanceInput] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_students(self):
        if len({e.student_id for e in self.entries}) != len(self.entries):
            raise ValueError("A student may appear only once")
        return self
