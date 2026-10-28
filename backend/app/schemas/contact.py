from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EducationSector(str, Enum):
    COMPREHENSIVE = "Comprehensive Schools"
    SENIOR = "Senior Schools"
    COLLEGE = "College"
    UNIVERSITY = "Universities"


class ProductEnquiryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    institution: str = Field(min_length=1, max_length=160)
    sector: EducationSector
    message: str = Field(min_length=10, max_length=4000)
