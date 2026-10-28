"""Templates are editable product defaults, never claims of national grading policy."""
from typing import Literal
from pydantic import Field, model_validator
from app.schemas.academic import Input
from app.services.grading_rules import GradingRules
from app.services.progression import ProgressionRules


class AcademicConfiguration(Input):
    progression_rules: ProgressionRules = Field(default_factory=ProgressionRules)
    grading_rules: GradingRules = Field(default_factory=GradingRules)
    structure: Literal['GROUPED', 'PROGRAMME'] = 'GROUPED'
    registration_mode: Literal['COHORT', 'INDIVIDUAL'] = 'COHORT'
    period_kind: Literal['TERM', 'SEMESTER', 'BLOCK'] = 'TERM'
    assessment_policy: Literal['NUMERIC', 'COMPETENCY', 'MIXED'] = 'NUMERIC'
    credits_enabled: bool = False
    competency_labels: list[str] = Field(default_factory=lambda: ['Needs support', 'Developing', 'Secure'], min_length=2, max_length=12)
    institution_policy_edits: bool = False

    @model_validator(mode='after')
    def labels(self):
        if self.grading_rules.enabled and self.assessment_policy=='COMPETENCY': raise ValueError('Competency-only institutions cannot enable numeric final grades or GPA')
        if self.grading_rules.gpa_enabled and not self.credits_enabled: raise ValueError('Enable course credits before GPA')
        if self.progression_rules.minimum_gpa is not None and not self.grading_rules.gpa_enabled: raise ValueError('Progression GPA threshold requires GPA enabled')
        if self.progression_rules.minimum_gpa is not None and self.progression_rules.minimum_gpa > self.grading_rules.gpa_scale: raise ValueError('Progression GPA threshold exceeds the configured GPA scale')
        if self.progression_rules.minimum_credits and not self.credits_enabled: raise ValueError('Credit progression requires course credits')
        if not set(self.progression_rules.competency_labels).issubset(self.competency_labels): raise ValueError('Progression competency outcomes must match institution rubric labels')
        self.competency_labels = [s.strip() for s in self.competency_labels]
        if any(not s or len(s) > 60 for s in self.competency_labels) or len(set(self.competency_labels)) != len(self.competency_labels):
            raise ValueError('Use distinct competency labels of 1 to 60 characters')
        return self


def template(kind):
    kind = getattr(kind, 'value', kind)
    data = {}
    if kind in {'UNIVERSITY', 'COLLEGE', 'TRAINING_INSTITUTION'}:
        data = dict(structure='PROGRAMME', registration_mode='INDIVIDUAL', period_kind='SEMESTER', credits_enabled=True, assessment_policy='MIXED')
    elif kind == 'KINDERGARTEN': data = dict(assessment_policy='COMPETENCY')
    elif kind == 'PRIMARY_SCHOOL': data = dict(assessment_policy='MIXED')
    return AcademicConfiguration(**data).model_dump()


def academic_configuration(institution):
    return AcademicConfiguration.model_validate({**template(institution.type), **(institution.academic_configuration or {})}).model_dump()
