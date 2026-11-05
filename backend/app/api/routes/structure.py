"""Education levels, assessment scales (platform admin) and CBE strands (institution admin)."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from app.api.routes.teaching import admin, commit, get_subject, scoped, staff
from app.core.deps import AuthContext, require_platform_admin, require_tenant_user
from app.core import tenancy
from app.db.session import get_db
from app.models.academic import AcademicClass
from app.models.curriculum import CatalogueUnit, Programme, StudyLevel
from app.models.institution import Institution, InstitutionStatus
from app.models.structure import EDUCATION_LEVELS, AssessmentScale, CurriculumStrand, InstitutionLevel
from app.schemas.academic import Input
from app.services.audit_service import record_audit
from app.services.structure import (ScaleInput, ensure_presets, level_view, scale_in_use, scale_view, usable_scale,
                                    write_levels)

router = APIRouter(prefix='/api', tags=['Levels and scales'])


def institution_or_404(db, institution_id, lock=False):
    q = db.query(Institution).filter_by(id=institution_id)
    row = (q.with_for_update() if lock else q).first()
    if not row: raise HTTPException(404, 'Institution not found')
    return row


def same_version(row, expected):
    """Compare an updated_at the client saw with the stored one, ignoring timezone formatting."""
    from datetime import datetime, timezone
    try:
        supplied = datetime.fromisoformat(expected.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return False
    current = row.updated_at
    supplied = supplied if supplied.tzinfo else supplied.replace(tzinfo=timezone.utc)
    current = current if current.tzinfo else current.replace(tzinfo=timezone.utc)
    return supplied == current


def writable(row):
    if row.status == InstitutionStatus.ARCHIVED: raise HTTPException(409, 'Archived institutions cannot be configured')


# --- Assessment scales -------------------------------------------------------

@router.get('/platform/assessment-scales')
def list_scales(institution_id: uuid.UUID | None = None, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    ensure_presets(db)
    db.commit()
    q = db.query(AssessmentScale).filter(AssessmentScale.institution_id.is_(None))
    rows = q.order_by(AssessmentScale.name).all()
    if institution_id:
        rows += db.query(AssessmentScale).filter_by(institution_id=institution_id).order_by(AssessmentScale.name).all()
    return [scale_view(db, row) for row in rows]


class NewScaleInput(ScaleInput):
    copied_from_id: uuid.UUID | None = None


@router.post('/platform/institutions/{institution_id}/assessment-scales', status_code=201)
def create_scale(institution_id: uuid.UUID, body: NewScaleInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    institution = institution_or_404(db, institution_id, lock=True)
    writable(institution)
    if body.copied_from_id: usable_scale(db, body.copied_from_id, institution.id)
    scale = AssessmentScale(institution_id=institution.id, name=body.name, kind=body.kind, copied_from_id=body.copied_from_id)
    db.add(scale)
    db.flush()
    write_levels(db, scale, body.levels)
    record_audit(db, ctx, 'assessment_scale.created', scale.id, institution.id, body.name)
    commit(db)
    return scale_view(db, scale, in_use=False)


class EditScaleInput(ScaleInput):
    expected_updated_at: str = Field(max_length=60)


@router.put('/platform/institutions/{institution_id}/assessment-scales/{scale_id}')
def edit_scale(institution_id: uuid.UUID, scale_id: uuid.UUID, body: EditScaleInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    writable(institution_or_404(db, institution_id))
    scale = db.query(AssessmentScale).filter_by(id=scale_id, institution_id=institution_id).with_for_update().first()
    if not scale: raise HTTPException(404, 'Assessment scale not found')
    if not same_version(scale, body.expected_updated_at): raise HTTPException(409, 'This scale changed. Reload before saving.')
    # Past results keep the bands they were marked with, but a scale that marks
    # already use must stay as it was so reports can name it truthfully.
    if scale_in_use(db, scale.id): raise HTTPException(409, 'Marks already use this scale. Copy it and assign the copy instead.')
    scale.name, scale.kind = body.name, body.kind
    write_levels(db, scale, body.levels)
    from datetime import datetime, timezone
    scale.updated_at = datetime.now(timezone.utc)
    record_audit(db, ctx, 'assessment_scale.updated', scale.id, institution_id, body.name)
    commit(db)
    return scale_view(db, scale, in_use=False)


# --- Education levels --------------------------------------------------------

class LevelInput(Input):
    level: Literal[EDUCATION_LEVELS]
    structure: Literal['GROUPED', 'PROGRAMME'] = 'GROUPED'
    period_kind: Literal['TERM', 'SEMESTER', 'BLOCK'] = 'TERM'
    scale_id: uuid.UUID | None = None
    terminology: dict[Literal['student_label', 'teacher_label', 'class_label', 'subject_label'], str] = Field(default_factory=dict)
    active: bool = True

    @model_validator(mode='after')
    def labels(self):
        self.terminology = {k: v.strip() for k, v in self.terminology.items() if v and v.strip()}
        if any(len(v) > 30 for v in self.terminology.values()): raise ValueError('Labels can be at most 30 characters')
        return self


class LevelsInput(Input):
    levels: list[LevelInput] = Field(max_length=len(EDUCATION_LEVELS))
    expected_updated_at: str = Field(max_length=60)

    @model_validator(mode='after')
    def distinct(self):
        if len({lv.level for lv in self.levels}) != len(self.levels): raise ValueError('Each level can be listed once')
        if not any(lv.active for lv in self.levels): raise ValueError('Choose at least one active level')
        return self


def levels_payload(db, institution):
    rows = db.query(InstitutionLevel).filter_by(institution_id=institution.id).all()
    rows.sort(key=lambda r: EDUCATION_LEVELS.index(r.level))
    return dict(levels=[level_view(db, row) for row in rows], updated_at=institution.updated_at)


@router.get('/platform/institutions/{institution_id}/levels')
def platform_levels(institution_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    return levels_payload(db, institution_or_404(db, institution_id))


def level_in_use(db, level):
    return any(db.query(model.id).filter(model.institution_id == level.institution_id, model.education_level_id == level.id).first()
               for model in (AcademicClass, Programme, StudyLevel, CatalogueUnit))


@router.put('/platform/institutions/{institution_id}/levels')
def save_levels(institution_id: uuid.UUID, body: LevelsInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    institution = institution_or_404(db, institution_id, lock=True)
    writable(institution)
    if not same_version(institution, body.expected_updated_at): raise HTTPException(409, 'Institution changed. Reload before saving.')
    current = {row.level: row for row in db.query(InstitutionLevel).filter_by(institution_id=institution.id).all()}
    wanted = {lv.level: lv for lv in body.levels}
    for level, row in current.items():
        if level not in wanted:
            if level_in_use(db, row): raise HTTPException(409, f'{level.replace("_", " ").title()} has classes or courses. Mark it inactive instead of removing it.')
            db.delete(row)
    changes = []
    for level, lv in wanted.items():
        usable_scale(db, lv.scale_id, institution.id)
        row = current.get(level)
        if row is None:
            row = InstitutionLevel(institution_id=institution.id, level=level)
            db.add(row)
        before = (row.structure, row.period_kind, row.scale_id, row.terminology, row.active)
        row.structure, row.period_kind, row.scale_id, row.terminology, row.active = lv.structure, lv.period_kind, lv.scale_id, lv.terminology, lv.active
        if before != (row.structure, row.period_kind, row.scale_id, row.terminology, row.active): changes.append(level)
    from datetime import datetime, timezone
    institution.updated_at = datetime.now(timezone.utc)
    record_audit(db, ctx, 'institution.levels_updated', institution.id, institution.id, ', '.join(changes)[:500])
    commit(db)
    return levels_payload(db, institution)


@router.get('/institution/levels')
def institution_levels(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    payload = levels_payload(db, db.get(Institution, ctx.institution_id))
    return [row for row in payload['levels'] if row['active']]


def owned_level(db, level_id, tenant):
    """Classes and courses may only point at an active level of their own institution."""
    if level_id is None: return None
    row = tenancy.owned(db, InstitutionLevel, level_id, tenant, not_found='Education level not found')
    if not row.active: raise HTTPException(422, 'This education level is not active for the institution')
    return row


# --- CBE strands -------------------------------------------------------------

class StrandInput(Input):
    code: str = Field(min_length=1, max_length=30, pattern=r'^[A-Za-z0-9._/-]+$')
    name: str = Field(min_length=1, max_length=160)
    parent_id: uuid.UUID | None = None
    position: int = Field(default=1, ge=1, le=1000)
    expected_updated_at: str | None = Field(default=None, max_length=60)


def strand_view(row):
    return dict(id=row.id, catalogue_id=row.catalogue_id, parent_id=row.parent_id, code=row.code, name=row.name,
                position=row.position, updated_at=row.updated_at)


def strands_for(db, ctx, course_id):
    rows = scoped(db, CurriculumStrand, ctx).filter_by(catalogue_id=course_id).order_by(CurriculumStrand.position, CurriculumStrand.code).all()
    return [strand_view(row) for row in rows]


def check_parent(db, ctx, course_id, parent_id, row=None):
    if parent_id is None: return
    parent = tenancy.owned(db, CurriculumStrand, parent_id, ctx.institution_id, not_found='Strand not found')
    if parent.catalogue_id != course_id: raise HTTPException(422, 'A sub-strand must belong to a strand of the same learning area')
    if parent.parent_id is not None: raise HTTPException(422, 'Strands go two levels deep: strand, then sub-strand')
    if row is not None and (parent.id == row.id or scoped(db, CurriculumStrand, ctx).filter_by(parent_id=row.id).first()):
        raise HTTPException(422, 'A strand with sub-strands cannot become a sub-strand')


@router.get('/institution/academic-structure/catalogue/{course_id}/strands')
def list_strands(course_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    tenancy.owned(db, CatalogueUnit, course_id, ctx.institution_id, not_found='Academic structure record not found')
    return strands_for(db, ctx, course_id)


@router.post('/institution/academic-structure/catalogue/{course_id}/strands', status_code=201)
def create_strand(course_id: uuid.UUID, body: StrandInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    tenancy.owned(db, CatalogueUnit, course_id, ctx.institution_id, lock=True, not_found='Academic structure record not found')
    check_parent(db, ctx, course_id, body.parent_id)
    row = CurriculumStrand(id=uuid.uuid4(), institution_id=ctx.institution_id, catalogue_id=course_id, parent_id=body.parent_id,
                           code=body.code.upper(), name=body.name, position=body.position)
    db.add(row)
    record_audit(db, ctx, 'curriculum.strand_created', row.id, ctx.institution_id, row.code)
    commit(db)
    return strand_view(row)


@router.put('/institution/academic-structure/strands/{strand_id}')
def edit_strand(strand_id: uuid.UUID, body: StrandInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = tenancy.owned(db, CurriculumStrand, strand_id, ctx.institution_id, lock=True, not_found='Strand not found')
    if not same_version(row, body.expected_updated_at or ''): raise HTTPException(409, 'This strand changed. Reload before saving.')
    check_parent(db, ctx, row.catalogue_id, body.parent_id, row)
    row.code, row.name, row.parent_id, row.position = body.code.upper(), body.name, body.parent_id, body.position
    record_audit(db, ctx, 'curriculum.strand_updated', row.id, ctx.institution_id, row.code)
    commit(db)
    return strand_view(row)


@router.get('/teaching/subjects/{subject_id}/strands')
def subject_strands(subject_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    subject = get_subject(db, subject_id, ctx)
    return strands_for(db, ctx, subject.catalogue_id) if subject.catalogue_id else []


def check_strand(db, ctx, subject, strand_id):
    """An assessment may point at a strand of its own learning area."""
    if strand_id is None: return
    strand = tenancy.owned(db, CurriculumStrand, strand_id, ctx.institution_id, not_found='Strand not found')
    if strand.catalogue_id != subject.catalogue_id: raise HTTPException(422, 'Choose a strand from this offering’s learning area')

