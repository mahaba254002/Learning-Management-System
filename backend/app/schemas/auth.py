import uuid

from pydantic import BaseModel, model_validator, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=1, max_length=1024)
    remember_me: bool = False


class StudentLoginRequest(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    student_id: str | None = Field(default=None, min_length=1, max_length=60, pattern=r"^[A-Za-z0-9._/-]+$")
    password: str = Field(min_length=1, max_length=1024)
    remember_me: bool = False
    model_config = {"extra": "forbid", "str_strip_whitespace": False}

    @model_validator(mode="after")
    def one_identity(self):
        if bool(self.email) == bool(self.student_id):
            raise ValueError("Provide either email or student ID")
        return self


class LoginResponse(BaseModel):
    must_change_password: bool
    user: "UserSummary"

class UserSummary(BaseModel):
    id: uuid.UUID
    username: str
    email: str | None = None
    first_name: str
    last_name: str
    role: str
    institution_id: uuid.UUID | None
    must_change_password: bool
    student_login_method: str = 'EMAIL'
    student_login_id: str | None = None

    # Concept note: `model_config` with from_attributes=True tells Pydantic
    # it's allowed to build this schema directly from a SQLAlchemy model
    # object's attributes (user.id, user.username, ...) instead of only
    # from a plain dict. Without this, passing a User model in would fail.
    model_config = {"from_attributes": True}


LoginResponse.model_rebuild()

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @model_validator(mode="after")
    def passwords_must_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirmation do not match")
        return self


class ChangePasswordResponse(BaseModel):
    message: str = "Password changed successfully."

###############
class ForgotPasswordRequest(BaseModel):
    email: str


class ForgotPasswordResponse(BaseModel):
    message: str = "If an account with that email exists, we've sent password reset instructions."


class ResetPasswordRequest(BaseModel):
    verification_id: uuid.UUID
    code: str = Field(min_length=6, max_length=6)
    new_password: str
    confirm_password: str

    @model_validator(mode="after")
    def passwords_must_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirmation do not match")
        return self


class ResetPasswordResponse(BaseModel):
    message: str = "Password reset successfully. You can now log in with your new password."
