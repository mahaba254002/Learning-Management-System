from typing import Literal
from pydantic import Field, model_validator
from app.schemas.academic import Input


class GradeBand(Input):
    minimum: float = Field(ge=0, le=100)
    label: str = Field(min_length=1, max_length=30)


class LearningSettings(Input):
    student_label: str = Field(default="Student", min_length=1, max_length=30)
    teacher_label: str = Field(default="Teacher", min_length=1, max_length=30)
    class_label: str = Field(default="Class", min_length=1, max_length=30)
    subject_label: str = Field(default="Subject", min_length=1, max_length=30)
    period_label: str = Field(default="Academic year", min_length=1, max_length=30)
    default_student_login: Literal["EMAIL", "STUDENT_ID"] = "EMAIL"
    grade_bands: list[GradeBand] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def distinct_bands(self):
        if self.grade_bands and (min(b.minimum for b in self.grade_bands) != 0 or len({b.minimum for b in self.grade_bands}) != len(self.grade_bands)):
            raise ValueError("Grade bands must include zero and have distinct minimum percentages")
        return self


def learning_settings(institution):
    kind = institution.type.value
    defaults = {}
    if kind in {"UNIVERSITY", "COLLEGE"}:
        defaults = dict(teacher_label="Lecturer", class_label="Cohort", subject_label="Course", period_label="Academic period")
    elif kind in {"PRIMARY_SCHOOL", "KINDERGARTEN"}:
        defaults = dict(student_label="Pupil", default_student_login="STUDENT_ID")
        if kind == 'KINDERGARTEN': defaults.update(student_label='Learner', subject_label='Learning area', class_label='Learning group')
    elif kind == 'TRAINING_INSTITUTION':
        defaults = dict(student_label='Trainee', teacher_label='Trainer', class_label='Cohort', subject_label='Module')
    return LearningSettings.model_validate({**defaults, **(institution.learning_settings or {})}).model_dump()


def grade_label(score, maximum, settings, snapshot=None):
    if score is None: return None
    percentage = float(score) / float(maximum) * 100
    bands = sorted(snapshot if snapshot is not None else settings.get("grade_bands", []), key=lambda b: b["minimum"], reverse=True)
    return next((b["label"] for b in bands if percentage >= b["minimum"]), None)
