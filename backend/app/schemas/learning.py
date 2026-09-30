from pydantic import Field, HttpUrl, field_validator, model_validator

from app.schemas.academic import Input


class LinkedInput(Input):
    link_url: HttpUrl | None = None

    @field_validator("link_url")
    @classmethod
    def safe_link(cls, value):
        if value and (len(str(value)) > 2000 or value.username or value.password):
            raise ValueError("Use a web link without embedded login details, up to 2000 characters")
        return value


class MaterialInput(LinkedInput):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=50000)
    published: bool = False

    @model_validator(mode="after")
    def content_required(self):
        if not self.body and not self.link_url:
            raise ValueError("Add lesson content or a resource link")
        return self


class SubmissionInput(LinkedInput):
    answer: str = Field(default="", max_length=50000)
    submit: bool = False
    expected_version: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def content_required(self):
        if self.submit and not self.answer and not self.link_url:
            raise ValueError("Add your answer or a document link before submitting")
        return self
