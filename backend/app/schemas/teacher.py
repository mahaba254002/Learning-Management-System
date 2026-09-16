from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.teacher import EmploymentType, Gender, TeacherStatus
from app.models.user import User
from app.models.teacher import Teacher


class TeacherSummary(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    username: str
    gender: Gender
    date_of_birth: date
    phone: str | None
    qualification: str
    specialization: str | None
    employment_type: EmploymentType
    status: TeacherStatus
    joined_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_join(cls, teacher: Teacher, user: User) -> "TeacherSummary":
        return cls(
            id=teacher.id,
            user_id=teacher.user_id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            username=user.username,
            gender=teacher.gender,
            date_of_birth=teacher.date_of_birth,
            phone=teacher.phone,
            qualification=teacher.qualification,
            specialization=teacher.specialization,
            employment_type=teacher.employment_type,
            status=teacher.status,
            joined_at=teacher.created_at,
        )
