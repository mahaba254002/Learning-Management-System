"""Education levels and the assessment scale library.

Presets are suggestions the platform admin can assign or copy. They are never
presented as official policy; the institution confirms its scale at onboarding."""
from decimal import Decimal
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, model_validator

from app.models.academic import Coursework
from app.models.structure import EDUCATION_LEVELS, AssessmentScale, InstitutionLevel, ScaleLevel
from app.schemas.academic import Input

LEVEL_NAMES = {
    'ECDE': 'ECDE (PP1–PP2)', 'LOWER_PRIMARY': 'Lower primary (Grades 1–3)', 'UPPER_PRIMARY': 'Upper primary (Grades 4–6)',
    'JUNIOR_SCHOOL': 'Junior school (Grades 7–9)', 'SENIOR_SCHOOL': 'Senior school (Grades 10–12)',
    'COLLEGE': 'College', 'TVET': 'TVET', 'UNIVERSITY': 'University',
}

# Levels an existing institution type is assumed to offer. Used for the first
# backfill and for new institutions; the platform admin can change them.
TYPE_LEVELS = {
    'KINDERGARTEN': ['ECDE'], 'PRIMARY_SCHOOL': ['LOWER_PRIMARY', 'UPPER_PRIMARY'], 'HIGH_SCHOOL': ['SENIOR_SCHOOL'],
    'COLLEGE': ['COLLEGE'], 'UNIVERSITY': ['UNIVERSITY'], 'TRAINING_INSTITUTION': ['TVET'], 'OTHER': [],
}


def level_defaults(level):
    if level in {'COLLEGE', 'UNIVERSITY', 'TVET'}:
        return dict(structure='PROGRAMME', period_kind='SEMESTER' if level != 'TVET' else 'TERM')
    return dict(structure='GROUPED', period_kind='TERM')


def _lv(code, label, minimum=None, points=None, descriptor=''):
    return dict(code=code, label=label, min_percent=minimum, points=points, descriptor=descriptor)


PRESET_SCALES = {
    'CBE_4': dict(name='CBE four levels', kind='COMPETENCY', levels=[
        _lv('EE', 'Exceeding expectations', 80, 4), _lv('ME', 'Meeting expectations', 50, 3),
        _lv('AE', 'Approaching expectations', 30, 2), _lv('BE', 'Below expectations', 0, 1)]),
    'CBE_8': dict(name='CBE eight levels', kind='COMPETENCY', levels=[
        _lv('EE1', 'Exceeding expectations 1', 90, 8), _lv('EE2', 'Exceeding expectations 2', 75, 7),
        _lv('ME1', 'Meeting expectations 1', 58, 6), _lv('ME2', 'Meeting expectations 2', 41, 5),
        _lv('AE1', 'Approaching expectations 1', 31, 4), _lv('AE2', 'Approaching expectations 2', 21, 3),
        _lv('BE1', 'Below expectations 1', 11, 2), _lv('BE2', 'Below expectations 2', 0, 1)]),
    'LETTER_A_E': dict(name='Letter grades A–E', kind='LETTER', levels=[
        _lv('A', 'A', 70), _lv('B', 'B', 60), _lv('C', 'C', 50), _lv('D', 'D', 40), _lv('E', 'E', 0)]),
    'GPA_4': dict(name='GPA 4.0', kind='GPA', levels=[
        _lv('A', 'A', 70, 4), _lv('B', 'B', 60, 3), _lv('C', 'C', 50, 2), _lv('D', 'D', 40, 1), _lv('E', 'E', 0, 0)]),
    'GPA_5': dict(name='GPA 5.0', kind='GPA', levels=[
        _lv('A', 'A', 70, 5), _lv('B', 'B', 60, 4), _lv('C', 'C', 50, 3), _lv('D', 'D', 45, 2), _lv('E', 'E', 40, 1), _lv('F', 'F', 0, 0)]),
    'TVET_COMPETENCE': dict(name='TVET competent / not yet competent', kind='COMPETENCY', levels=[
        _lv('C', 'Competent'), _lv('NYC', 'Not yet competent')]),
    'PERCENT': dict(name='Percentage only', kind='PERCENT', levels=[]),
}


class ScaleLevelInput(Input):
    code: str = Field(min_length=1, max_length=20, pattern=r'^[A-Za-z0-9+._-]+$')
    label: str = Field(min_length=1, max_length=60)
    descriptor: str = Field(default='', max_length=255)
    min_percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    points: Decimal | None = Field(default=None, ge=0, le=100, max_digits=6, decimal_places=2)


class ScaleInput(Input):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal['COMPETENCY', 'LETTER', 'GPA', 'PERCENT']
    levels: list[ScaleLevelInput] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def valid_levels(self):
        levels = self.levels
        if self.kind == 'PERCENT':
            if levels: raise ValueError('A percentage-only scale has no levels')
            return self
        if len(levels) < 2: raise ValueError('A scale needs at least two levels')
        if len({lv.code.upper() for lv in levels}) != len(levels): raise ValueError('Each level needs a different code')
        if len({lv.label for lv in levels}) != len(levels): raise ValueError('Each level needs a different label')
        with_range = [lv.min_percent is not None for lv in levels]
        if self.kind in {'LETTER', 'GPA'} and not all(with_range): raise ValueError('Every level needs a minimum percentage')
        if any(with_range) and not all(with_range): raise ValueError('Give a minimum percentage for every level, or for none')
        if all(with_range):
            minimums = [lv.min_percent for lv in levels]
            if len(set(minimums)) != len(minimums) or min(minimums) != 0: raise ValueError('Minimum percentages must differ and one must be 0')
            if minimums != sorted(minimums, reverse=True): raise ValueError('List levels from highest to lowest')
        if self.kind == 'GPA':
            if any(lv.points is None for lv in levels): raise ValueError('Every GPA level needs points')
            points = [lv.points for lv in levels]
            if points != sorted(points, reverse=True): raise ValueError('Points cannot rise as marks fall')
        for lv in levels: lv.code = lv.code.upper()
        return self


def ensure_presets(db):
    """Create any missing preset scales. Safe to call repeatedly."""
    existing = {row.code for row in db.query(AssessmentScale).filter(AssessmentScale.institution_id.is_(None)).all()}
    added = False
    for code, data in PRESET_SCALES.items():
        if code in existing: continue
        scale = AssessmentScale(code=code, name=data['name'], kind=data['kind'])
        db.add(scale)
        db.flush()
        write_levels(db, scale, [ScaleLevelInput(**lv) for lv in data['levels']])
        added = True
    if added: db.flush()


def write_levels(db, scale, levels):
    db.query(ScaleLevel).filter_by(scale_id=scale.id).delete()
    db.flush()
    upper = Decimal('100')
    for position, lv in enumerate(levels, start=1):
        maximum = None
        if lv.min_percent is not None:
            maximum = upper
            upper = lv.min_percent - Decimal('0.01')
        db.add(ScaleLevel(scale_id=scale.id, code=lv.code, label=lv.label, descriptor=lv.descriptor,
                          min_percent=lv.min_percent, max_percent=maximum, points=lv.points, position=position))


def scale_in_use(db, scale_id):
    return db.query(Coursework.id).filter(Coursework.scale_id == scale_id).first() is not None


def scale_view(db, scale, in_use=None):
    levels = db.query(ScaleLevel).filter_by(scale_id=scale.id).order_by(ScaleLevel.position).all()
    return dict(id=scale.id, code=scale.code, name=scale.name, kind=scale.kind, preset=scale.institution_id is None,
                institution_id=scale.institution_id, copied_from_id=scale.copied_from_id, updated_at=scale.updated_at,
                in_use=scale_in_use(db, scale.id) if in_use is None else in_use,
                levels=[dict(code=lv.code, label=lv.label, descriptor=lv.descriptor,
                             min_percent=lv.min_percent, max_percent=lv.max_percent, points=lv.points) for lv in levels])


def usable_scale(db, scale_id, institution_id):
    """A level may use a preset or one of its own institution's scales."""
    if scale_id is None: return None
    scale = db.get(AssessmentScale, scale_id)
    if scale is None or scale.institution_id not in {None, institution_id}:
        raise HTTPException(404, 'Assessment scale not found')
    return scale


def level_view(db, row):
    scale = db.get(AssessmentScale, row.scale_id) if row.scale_id else None
    return dict(id=row.id, level=row.level, name=LEVEL_NAMES[row.level], structure=row.structure, period_kind=row.period_kind,
                terminology=row.terminology or {}, active=row.active, updated_at=row.updated_at,
                scale=scale_view(db, scale) if scale else None)


def create_default_levels(db, institution):
    for level in TYPE_LEVELS.get(getattr(institution.type, 'value', institution.type), []):
        db.add(InstitutionLevel(institution_id=institution.id, level=level, **level_defaults(level)))


def class_scale(db, cls):
    """The scale chosen for the class's education level, if any."""
    if cls is None or not cls.education_level_id: return None
    level = db.get(InstitutionLevel, cls.education_level_id)
    if level is None or level.institution_id != cls.institution_id or not level.scale_id: return None
    return db.get(AssessmentScale, level.scale_id)


def scale_bands(db, scale):
    """Copy a scale into the grading-band format stored on each assessment."""
    levels = db.query(ScaleLevel).filter_by(scale_id=scale.id).order_by(ScaleLevel.position).all()
    if not levels or any(lv.min_percent is None for lv in levels): return None
    return [dict(minimum=float(lv.min_percent), label=lv.code) for lv in levels]


def scale_labels(db, scale):
    return [lv.label for lv in db.query(ScaleLevel).filter_by(scale_id=scale.id).order_by(ScaleLevel.position).all()]


assert set(LEVEL_NAMES) == set(EDUCATION_LEVELS)
