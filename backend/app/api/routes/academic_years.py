"""Institution calendars, closure review and reviewed class-to-class promotion."""
import hashlib
import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal
import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy.orm import Session
from app.api.routes.teaching import admin, scoped, commit
from app.core.config import settings
from app.core.deps import AuthContext
from app.core.security import decode_token
from app.db.session import get_db
from app.models.academic import AcademicClass, Coursework, Enrollment, Score, Subject
from app.models.audit import AuditEvent
from app.models.institution import Institution
from app.models.pilot import AcademicYear, AcademicPeriod
from app.schemas.academic import Input
from app.services.audit_service import record_audit

router = APIRouter(prefix='/api/institution/academic-years', tags=['Academic calendar'])


class Dates(Input):
    start_date: date
    end_date: date

    @model_validator(mode='after')
    def ordered(self):
        if self.end_date < self.start_date: raise ValueError('End date must follow start date')
        return self


class YearInput(Dates):
    name: str = Field(min_length=1, max_length=30)


class PeriodInput(Dates):
    name: str = Field(min_length=1, max_length=60)


class Transition(Input):
    status: Literal['ACTIVE', 'CLOSED']
    confirmation: str = Field(max_length=80)


class Mapping(Input):
    source_class_id: uuid.UUID
    target_class_id: uuid.UUID | None = None


class Promotion(Input):
    target_year_id: uuid.UUID
    mappings: list[Mapping] = Field(min_length=1, max_length=500)
    preview_token: str | None = Field(default=None, max_length=3000)


def year_row(db, ctx, identity):
    row = scoped(db, AcademicYear, ctx).filter_by(id=identity).with_for_update().first()
    if not row: raise HTTPException(404, 'Academic year not found')
    return row


def review(db, ctx, year):
    classes = scoped(db, AcademicClass, ctx).filter_by(academic_year=year.name).all()
    ids = [c.id for c in classes]
    subjects = scoped(db, Subject, ctx).filter(Subject.class_id.in_(ids)).all()
    works = scoped(db, Coursework, ctx).filter(Coursework.subject_id.in_([s.id for s in subjects])).all()
    published = [w for w in works if w.published]
    enrollments = scoped(db, Enrollment, ctx).filter(Enrollment.class_id.in_(ids), Enrollment.active.is_(True)).all()
    rosters = defaultdict(set)
    for enrollment in enrollments: rosters[enrollment.class_id].add(enrollment.student_id)
    subject_classes = {s.id: s.class_id for s in subjects}
    marks = scoped(db, Score, ctx).filter(Score.coursework_id.in_([w.id for w in works])).all()
    graded = defaultdict(set)
    for mark in marks: graded[mark.coursework_id].add(mark.student_id)
    from app.models.curriculum import CourseRegistration
    registrations = scoped(db, CourseRegistration, ctx).filter(CourseRegistration.subject_id.in_([s.id for s in subjects]), CourseRegistration.active.is_(True)).all()
    registered = defaultdict(set)
    for registration in registrations: registered[registration.subject_id].add(registration.student_id)
    individual = {s.id for s in subjects if s.registration_mode == 'INDIVIDUAL'}
    missing = sum(len((rosters[subject_classes[w.subject_id]] & registered[w.subject_id] if w.subject_id in individual else rosters[subject_classes[w.subject_id]]) - graded[w.id]) for w in published)
    return dict(classes=len(classes), students=scoped(db, Enrollment, ctx).filter(Enrollment.class_id.in_(ids), Enrollment.active.is_(True)).count(),
        assessments=len(works), unpublished_assessments=sum(not w.published for w in works),
        unreleased_results=sum(not w.grades_released for w in published),
        missing_scores=missing,
        unassigned_classes=sum(c.supervisor_id is None for c in classes),
        scores=len(marks))


@router.get('')
def years(db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    rows = scoped(db, AcademicYear, ctx).order_by(AcademicYear.start_date.desc()).all()
    existing = {r.name for r in rows}
    legacy = sorted({r[0] for r in scoped(db, AcademicClass, ctx).with_entities(AcademicClass.academic_year).distinct().all()} - existing)
    return dict(years=[dict(id=r.id, name=r.name, start_date=r.start_date, end_date=r.end_date, status=r.status,
        periods=[dict(id=p.id, name=p.name, start_date=p.start_date, end_date=p.end_date) for p in scoped(db, AcademicPeriod, ctx).filter_by(year_id=r.id).order_by(AcademicPeriod.start_date).all()],
        readiness=review(db, ctx, r)) for r in rows], unconfigured_years=legacy)


@router.post('', status_code=201)
def create(body: YearInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    # Serialize calendar creation/transitions per institution, including a first year.
    db.query(Institution).filter_by(id=ctx.institution_id).with_for_update().one()
    overlap = scoped(db, AcademicYear, ctx).filter(AcademicYear.start_date <= body.end_date, AcademicYear.end_date >= body.start_date).first()
    if overlap: raise HTTPException(409, 'These dates overlap another academic year')
    row = AcademicYear(id=uuid.uuid4(), institution_id=ctx.institution_id, **body.model_dump())
    db.add(row)
    record_audit(db, ctx, 'academic_year.created', row.id, ctx.institution_id, body.name)
    commit(db)
    return dict(id=row.id)


@router.post('/{year_id}/periods', status_code=201)
def period(year_id: uuid.UUID, body: PeriodInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    year = year_row(db, ctx, year_id)
    if year.status == 'CLOSED': raise HTTPException(409, 'This year is closed')
    if body.start_date < year.start_date or body.end_date > year.end_date: raise HTTPException(422, 'Term or semester dates must be inside the academic year')
    if scoped(db, AcademicPeriod, ctx).filter(AcademicPeriod.year_id == year.id, AcademicPeriod.start_date <= body.end_date, AcademicPeriod.end_date >= body.start_date).first():
        raise HTTPException(409, 'These dates overlap another term or semester')
    row = AcademicPeriod(id=uuid.uuid4(), institution_id=ctx.institution_id, year_id=year.id, **body.model_dump())
    db.add(row)
    record_audit(db, ctx, 'academic_period.created', row.id, ctx.institution_id, body.name)
    commit(db)
    return dict(id=row.id)


@router.post('/{year_id}/transition')
def transition(year_id: uuid.UUID, body: Transition, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    db.query(Institution).filter_by(id=ctx.institution_id).with_for_update().one()
    year = year_row(db, ctx, year_id)
    if body.confirmation != f'{body.status} {year.name}': raise HTTPException(422, 'Enter the displayed confirmation phrase')
    if year.status == 'CLOSED' or year.status == body.status: raise HTTPException(409, 'This transition is no longer available')
    if body.status == 'ACTIVE':
        if scoped(db, AcademicYear, ctx).filter_by(status='ACTIVE').first(): raise HTTPException(409, 'Close the current active year before activating another')
        if not scoped(db, AcademicPeriod, ctx).filter_by(year_id=year.id).first(): raise HTTPException(409, 'Add at least one term or semester before activation')
    else:
        if year.status != 'ACTIVE': raise HTTPException(409, 'Activate the year before closing it')
        if review(db, ctx, year)['unreleased_results']: raise HTTPException(409, 'Review and release published assessment results before closing the year')
        if review(db, ctx, year)['missing_scores']: raise HTTPException(409, 'Complete missing marks for published assessments before closing the year')
    year.status = body.status
    record_audit(db, ctx, 'academic_year.' + body.status.lower(), year.id, ctx.institution_id, year.name)
    commit(db)
    return dict(status=year.status)


def promotion_plan(db, ctx, source, body):
    from app.services.progression import rules
    if rules(db, ctx.institution_id)["enabled"]:
        raise HTTPException(409, "Individual progression is enabled. Use Student progression to review each learner before advancement or completion.")
    target = year_row(db, ctx, body.target_year_id)
    if source.status != 'CLOSED' or target.status == 'CLOSED' or target.start_date <= source.end_date:
        raise HTTPException(409, 'Promote from a closed year to a later open year')
    if db.query(AuditEvent.id).filter_by(institution_id=ctx.institution_id, action='academic_year.promoted', target_id=str(source.id)).first():
        raise HTTPException(409, 'This year has already been promoted')
    sources = {c.id: c for c in scoped(db, AcademicClass, ctx).filter_by(academic_year=source.name).all()}
    targets = {c.id: c for c in scoped(db, AcademicClass, ctx).filter_by(academic_year=target.name).all()}
    source_ids = [m.source_class_id for m in body.mappings]
    if len(set(source_ids)) != len(source_ids) or set(source_ids) != set(sources): raise HTTPException(422, 'Map every source class exactly once')
    moves, summary, state = [], [], []
    for m in body.mappings:
        if m.target_class_id is not None and m.target_class_id not in targets: raise HTTPException(404, 'Destination class not found in the target year')
        enrolled = scoped(db, Enrollment, ctx).filter_by(class_id=m.source_class_id, active=True).order_by(Enrollment.student_id).all()
        state.extend((str(e.id), str(e.student_id), str(e.updated_at)) for e in enrolled)
        summary.append(dict(source=sources[m.source_class_id].name, target=targets[m.target_class_id].name if m.target_class_id else 'Completed / leaving', students=len(enrolled)))
        if m.target_class_id:
            moves.extend((e.student_id, m.target_class_id) for e in enrolled)
    if len(set(moves)) != len(moves): raise HTTPException(409, 'A student would be enrolled twice in the same destination')
    destination = scoped(db, Enrollment, ctx).filter(Enrollment.class_id.in_(targets)).order_by(Enrollment.id).all()
    state.extend((str(e.id), str(e.student_id), str(e.updated_at), e.active) for e in destination)
    fingerprint = hashlib.sha256(json.dumps(dict(body=body.model_dump(mode='json', exclude={'preview_token'}), state=state,
        classes=[(str(c.id), str(c.updated_at)) for c in sorted([*sources.values(), *targets.values()], key=lambda c: str(c.id))]), sort_keys=True).encode()).hexdigest()
    return moves, summary, fingerprint


@router.post('/{year_id}/promotion/preview')
def preview_promotion(year_id: uuid.UUID, body: Promotion, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    source = year_row(db, ctx, year_id)
    moves, summary, fingerprint = promotion_plan(db, ctx, source, body)
    token = jwt.encode(dict(type='promotion', sub=str(ctx.actor_user_id or ctx.user_id), user=str(ctx.user_id), source=str(source.id), sha=fingerprint,
        exp=datetime.now(timezone.utc) + timedelta(minutes=10)), settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return dict(summary=summary, enrollments=len(moves), preview_token=token)


@router.post('/{year_id}/promotion/commit')
def promote(year_id: uuid.UUID, body: Promotion, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    db.query(Institution).filter_by(id=ctx.institution_id).with_for_update().one()
    source = year_row(db, ctx, year_id)
    # All writes lock the year before their class; closed source data is immutable.
    destination = year_row(db, ctx, body.target_year_id)
    scoped(db, AcademicClass, ctx).filter_by(academic_year=destination.name).order_by(AcademicClass.id).with_for_update().all()
    moves, summary, fingerprint = promotion_plan(db, ctx, source, body)
    try:
        token = decode_token(body.preview_token or '')
        if any(token.get(k) != v for k, v in dict(type='promotion', sub=str(ctx.actor_user_id or ctx.user_id), user=str(ctx.user_id), source=str(source.id), sha=fingerprint).items()): raise ValueError()
    except (jwt.PyJWTError, ValueError): raise HTTPException(409, 'The promotion plan expired or changed. Review it again.')
    for student_id, class_id in moves:
        row = scoped(db, Enrollment, ctx).filter_by(student_id=student_id, class_id=class_id).first()
        if row: row.active = True
        else: db.add(Enrollment(institution_id=ctx.institution_id, student_id=student_id, class_id=class_id))
    record_audit(db, ctx, 'academic_year.promoted', source.id, ctx.institution_id, f'{len(moves)} enrollments into {body.target_year_id}; historical enrollments retained')
    commit(db)
    return dict(enrollments=len(moves), message='Promotion completed. Original enrollments, attendance and marks are retained as history.')
