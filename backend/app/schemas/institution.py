import uuid

from pydantic import BaseModel, Field, field_validator

from app.models.institution import InstitutionStatus, InstitutionType


class InstitutionCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    code: str = Field(min_length=2, max_length=20)
    type: InstitutionType
    country: str = Field(min_length=2, max_length=100)
    address: str | None = None
    official_email: str | None = None
    phone: str | None = None
    website: str | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        # Institution codes become part of every username at this
        # institution (first.last.code), so we normalize to lowercase,
        # no spaces — keeps usernames predictable and clean.
        v = v.strip().lower().replace(" ", "-")
        if not v.replace("-", "").isalnum():
            raise ValueError("code must contain only letters, numbers, and hyphens")
        return v


class InstitutionResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    type: InstitutionType
    country: str
    address: str | None
    official_email: str | None
    phone: str | None
    website: str | None
    status: InstitutionStatus

    model_config = {"from_attributes": True}


class VerificationRequiredResponse(BaseModel):
    """Returned after step 1 (request-create/request-delete). The client
    must show a 'enter the code we sent you' screen and then call the
    confirm endpoint with this verification_id + the code."""

    verification_id: uuid.UUID
    message: str = "A verification code has been sent to your email."


class ConfirmCodeRequest(BaseModel):
    verification_id: uuid.UUID
    code: str = Field(min_length=6, max_length=6)


class InstitutionAdminCreateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str | None = None


class InstitutionAdminCreatedResponse(BaseModel):
    id: uuid.UUID
    username: str
    first_name: str
    last_name: str
    temporary_password: str
    institution_id: uuid.UUID
    message: str = (
        "Share these credentials securely with the institution admin. "
        "This is the only time the temporary password will be shown."
    )


class PlatformStats(BaseModel):
    total_institutions: int
    active_institutions: int
    archived_institutions: int
    total_users: int
    users_by_role: dict[str, int]