import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.invitation import InvitationStatus


class SendTeacherInvitationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class InvitationSummary(BaseModel):
    id: uuid.UUID
    email: str
    status: InvitationStatus
    created_at: datetime
    expires_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class InvitationPublicView(BaseModel):
    """What an anonymous invitee sees when they open their link — no
    internal IDs or institution-sensitive info beyond what's needed."""

    institution_name: str
    invited_role: str
    email: str
    status: InvitationStatus
    expires_at: datetime


class TeacherSubmissionRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    gender: str
    date_of_birth: str  # ISO date string (YYYY-MM-DD), validated in the route
    phone: str | None = None
    qualification: str = Field(min_length=1, max_length=255)
    specialization: str | None = None
    employment_type: str


class InvitationApprovedResponse(BaseModel):
    id: uuid.UUID
    username: str
    temporary_password: str
    credentials_emailed: bool
    message: str = (
        "Teacher account created. Share these credentials securely — "
        "this is the only time the temporary password will be shown."
    )