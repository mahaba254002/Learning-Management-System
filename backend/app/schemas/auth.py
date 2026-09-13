import uuid

from pydantic import BaseModel, model_validator, Field


class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    must_change_password: bool
    user: "UserSummary"

class UserSummary(BaseModel):
    id: uuid.UUID
    username: str
    first_name: str
    last_name: str
    role: str
    institution_id: uuid.UUID | None

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