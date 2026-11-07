import uuid

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
    section: str = Field(default="", max_length=120)
    file_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def content_required(self):
        self.section = self.section.strip()
        if not self.body and not self.link_url and not self.file_id:
            raise ValueError("Add lesson content, a resource link or a file")
        return self


class SubmissionInput(LinkedInput):
    answer: str = Field(default="", max_length=50000)
    submit: bool = False
    expected_version: int = Field(default=0, ge=0)
    file_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def content_required(self):
        if self.submit and not self.answer and not self.link_url and not self.file_id:
            raise ValueError("Add your answer, a document link or a file before submitting")
        return self
