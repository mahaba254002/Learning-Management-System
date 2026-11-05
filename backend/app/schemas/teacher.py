from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class TeacherSummary(BaseModel):
    """A teacher's login plus their staff record. Built by services.staff.teacher_summary."""
    id: uuid.UUID  # staff record id
    user_id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None
    username: str
    staff_number: str
    job_title: str
    department_id: uuid.UUID | None
    gender: str | None
    date_of_birth: date | None
    phone: str | None
    qualification: str | None
    specialization: str | None
    employment_type: str
    status: str  # staff record status: ACTIVE, ON_LEAVE or INACTIVE
    account_status: str  # sign-in status: ACTIVE, SUSPENDED, DEACTIVATED, ARCHIVED
    joined_at: datetime
