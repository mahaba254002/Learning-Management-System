"""Timetables: the administrator enters them by hand; teachers and students use them once published.

Clashes (a teacher or class booked twice, or a teacher marked unavailable) are
refused. The administrator may save anyway with a reason, for example a combined
class, and the reason is kept on the lesson and in the audit trail."""
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.routes.teaching import active_teacher, commit, missing, taught_subject_ids
from app.core.deps import AuthContext, require_role, require_tenant_user
from app.core.tenancy import scoped
from app.db.session import get_db
from app.models.academic import AcademicClass, Enrollment, Student, Subject
from app.models.curriculum import CourseRegistration
from app.models.management import StaffMember
from app.models.pilot import AcademicPeriod, AcademicYear
from app.models.structure import OfferingTeacher
from app.models.timetable import LessonChange, TeacherUnavailability, TimetableEntry, TimetableSlot, TimetableTerm
from app.models.user import User, UserRole, UserStatus
from app.schemas.academic import Input
from app.services.audit_service import record_audit

router = APIRouter(prefix="/api/timetable", tags=["Timetable"])
admin = require_role(UserRole.INSTITUTION_ADMIN)
DAYS = {1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Friday', 6: 'Saturday', 7: 'Sunday'}
Weekday = Field(ge=1, le=7)


def hm(value):
    return value.strftime('%H:%M') if value else None


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def name(user):
    return f'{user.first_name} {user.last_name}' if user else None


def clash_error(clashes):
    raise HTTPException(409, dict(message='This lesson clashes with the timetable. Change it, or save anyway with a reason.', clashes=clashes))


# --- Terms -------------------------------------------------------------------------

def get_period(db, ctx, period_id):
    period = scoped(db, AcademicPeriod, ctx).filter_by(id=period_id).first()
    if not period:
        missing()
    return period


def get_term(db, ctx, period_id, *, create=False, lock=False):
    get_period(db, ctx, period_id)
    q = scoped(db, TimetableTerm, ctx).filter_by(period_id=period_id)
    term = (q.with_for_update() if lock else q).first()
    if term is None and create:
        term = TimetableTerm(institution_id=ctx.institution_id, period_id=period_id, weekdays=[1, 2, 3, 4, 5])
        db.add(term)
        db.flush()
    return term


def slot_runs(slot, weekday, term_days):
    return weekday in (slot.weekdays or term_days)


def slot_view(slot):
    return dict(id=slot.id, label=slot.label, start_time=hm(slot.start_time), end_time=hm(slot.end_time),
                is_break=slot.is_break, weekdays=slot.weekdays or [])


@router.get('/terms')
def terms(db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    periods = scoped(db, AcademicPeriod, ctx).join(AcademicYear, AcademicYear.id == AcademicPeriod.year_id).filter(
        AcademicYear.institution_id == ctx.institution_id).with_entities(AcademicPeriod, AcademicYear).order_by(AcademicPeriod.start_date.desc()).all()
    settings = {t.period_id: t for t in scoped(db, TimetableTerm, ctx).all()}
    counts = dict(db.query(TimetableEntry.period_id, func.count(TimetableEntry.id)).filter(
        TimetableEntry.institution_id == ctx.institution_id).group_by(TimetableEntry.period_id).all())
    today = date.today()
    return [dict(id=p.id, name=p.name, year=y.name, start_date=p.start_date, end_date=p.end_date, current=p.start_date <= today <= p.end_date,
                 published=bool(settings.get(p.id) and settings[p.id].published_at), lessons=counts.get(p.id, 0)) for p, y in periods]


def open_classes(db, ctx, period):
    year = scoped(db, AcademicYear, ctx).filter_by(id=period.year_id).first()
    q = scoped(db, AcademicClass, ctx)
    if year is not None:
        q = q.filter(AcademicClass.academic_year == year.name)
    return q.order_by(AcademicClass.name, AcademicClass.stream).all()


@router.get('/terms/{period_id}')
def term_detail(period_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    period = get_period(db, ctx, period_id)
    term = get_term(db, ctx, period_id)
    slots = scoped(db, TimetableSlot, ctx).filter_by(period_id=period_id).order_by(TimetableSlot.start_time, TimetableSlot.label).all()
    teachers = scoped(db, User, ctx).join(StaffMember, (StaffMember.user_id == User.id) & (StaffMember.institution_id == User.institution_id)).filter(
        User.role == UserRole.TEACHER, User.status == UserStatus.ACTIVE, StaffMember.status == 'ACTIVE').order_by(User.first_name, User.last_name).all()
    away = scoped(db, TeacherUnavailability, ctx).filter_by(period_id=period_id).order_by(
        TeacherUnavailability.weekday, TeacherUnavailability.start_time).all()
    names = {t.id: name(t) for t in teachers}
    return dict(period=dict(id=period.id, name=period.name, start_date=period.start_date, end_date=period.end_date),
                weekdays=term.weekdays if term else [1, 2, 3, 4, 5], published=bool(term and term.published_at),
                published_at=term.published_at if term else None, slots=[slot_view(s) for s in slots],
                classes=[dict(id=c.id, name=f"{c.name}{' ' + c.stream if c.stream else ''}") for c in open_classes(db, ctx, period)],
                teachers=[dict(id=t.id, name=names[t.id]) for t in teachers],
                unavailability=[dict(id=u.id, teacher_id=u.teacher_id, teacher_name=names.get(u.teacher_id), weekday=u.weekday,
                                     start_time=hm(u.start_time), end_time=hm(u.end_time), reason=u.reason) for u in away])


class TermInput(Input):
    weekdays: list[int] = Field(min_length=1, max_length=7)

    @model_validator(mode='after')
    def valid_days(self):
        if any(d < 1 or d > 7 for d in self.weekdays) or len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError('Choose each teaching day once')
        self.weekdays = sorted(self.weekdays)
        return self


@router.put('/terms/{period_id}')
def save_term(period_id: uuid.UUID, body: TermInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    term = get_term(db, ctx, period_id, create=True, lock=True)
    dropped = set(term.weekdays) - set(body.weekdays)
    if dropped and scoped(db, TimetableEntry, ctx).filter(TimetableEntry.period_id == period_id, TimetableEntry.weekday.in_(dropped)).first():
        raise HTTPException(409, f'Remove the lessons on {", ".join(DAYS[d] for d in sorted(dropped))} first')
    term.weekdays = body.weekdays
    commit(db)
    return dict(weekdays=term.weekdays)


class PublishInput(Input):
    published: bool


@router.post('/terms/{period_id}/publish')
def publish(period_id: uuid.UUID, body: PublishInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    term = get_term(db, ctx, period_id, create=True, lock=True)
    if body.published and not scoped(db, TimetableEntry, ctx).filter_by(period_id=period_id).first():
        raise HTTPException(409, 'Add lessons before publishing the timetable')
    term.published_at = datetime.now(timezone.utc) if body.published else None
    record_audit(db, ctx, 'timetable.published' if body.published else 'timetable.unpublished', period_id, ctx.institution_id)
    commit(db)
    return dict(published=body.published)


@router.post('/terms/{period_id}/copy')
def copy_term(period_id: uuid.UUID, source_period_id: uuid.UUID = Query(), db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    """Start a term from another term's bell schedule and lessons. Only into an empty term."""
    if source_period_id == period_id:
        raise HTTPException(400, 'Choose a different term to copy from')
    target = get_term(db, ctx, period_id, create=True, lock=True)
    period = get_period(db, ctx, period_id)
    source = get_term(db, ctx, source_period_id)
    if scoped(db, TimetableSlot, ctx).filter_by(period_id=period_id).first():
        raise HTTPException(409, 'This term already has a bell schedule. Copy only into an empty term.')
    target.weekdays = source.weekdays if source else target.weekdays
    mapping = {}
    for slot in scoped(db, TimetableSlot, ctx).filter_by(period_id=source_period_id).all():
        copy = TimetableSlot(institution_id=ctx.institution_id, period_id=period_id, label=slot.label, start_time=slot.start_time,
                             end_time=slot.end_time, is_break=slot.is_break, weekdays=list(slot.weekdays or []))
        db.add(copy)
        mapping[slot.id] = copy
    db.flush()
    classes = {c.id for c in open_classes(db, ctx, period)}
    copied = skipped = 0
    for entry in scoped(db, TimetableEntry, ctx).filter_by(period_id=source_period_id).all():
        subject = scoped(db, Subject, ctx).filter_by(id=entry.subject_id).first()
        # Lessons for classes or offerings that do not run this term are left out.
        if subject is None or subject.class_id not in classes or (subject.period_id and subject.period_id != period_id):
            skipped += 1
            continue
        db.add(TimetableEntry(institution_id=ctx.institution_id, period_id=period_id, slot_id=mapping[entry.slot_id].id, weekday=entry.weekday,
                              subject_id=entry.subject_id, class_id=entry.class_id, teacher_id=entry.teacher_id, override_reason=entry.override_reason))
        copied += 1
    record_audit(db, ctx, 'timetable.copied', period_id, ctx.institution_id, f'{copied} lessons from another term')
    commit(db)
    return dict(slots=len(mapping), lessons=copied, skipped=skipped)


# --- Bell schedule -----------------------------------------------------------------

class SlotInput(Input):
    label: str = Field(min_length=1, max_length=40)
    start_time: time
    end_time: time
    is_break: bool = False
    weekdays: list[int] = Field(default_factory=list, max_length=7)

    @model_validator(mode='after')
    def valid(self):
        if self.end_time <= self.start_time:
            raise ValueError('The end time must be after the start time')
        if any(d < 1 or d > 7 for d in self.weekdays) or len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError('Choose each day once')
        self.weekdays = sorted(self.weekdays)
        return self


def check_slot(db, ctx, period_id, body, term_days, exclude=None):
    for other in scoped(db, TimetableSlot, ctx).filter_by(period_id=period_id).all():
        if other.id == exclude:
            continue
        shared = set(body.weekdays or term_days) & set(other.weekdays or term_days)
        if shared and overlaps(body.start_time, body.end_time, other.start_time, other.end_time):
            raise HTTPException(409, f'{body.label} overlaps {other.label} ({hm(other.start_time)}-{hm(other.end_time)})')


@router.post('/terms/{period_id}/slots', status_code=201)
def add_slot(period_id: uuid.UUID, body: SlotInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    term = get_term(db, ctx, period_id, create=True, lock=True)
    check_slot(db, ctx, period_id, body, term.weekdays)
    slot = TimetableSlot(institution_id=ctx.institution_id, period_id=period_id, **body.model_dump())
    db.add(slot)
    commit(db)
    return slot_view(slot)


def get_slot(db, ctx, slot_id, lock=False):
    q = scoped(db, TimetableSlot, ctx).filter_by(id=slot_id)
    slot = (q.with_for_update() if lock else q).first()
    if not slot:
        missing()
    return slot


@router.put('/slots/{slot_id}')
def edit_slot(slot_id: uuid.UUID, body: SlotInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    slot = get_slot(db, ctx, slot_id, lock=True)
    term = get_term(db, ctx, slot.period_id, create=True, lock=True)
    check_slot(db, ctx, slot.period_id, body, term.weekdays, exclude=slot.id)
    used = scoped(db, TimetableEntry, ctx).filter_by(slot_id=slot.id)
    if body.is_break and used.first():
        raise HTTPException(409, 'Lessons are placed in this period. Move them before making it a break.')
    if body.weekdays and used.filter(TimetableEntry.weekday.not_in(body.weekdays)).first():
        raise HTTPException(409, 'Lessons are placed in this period on a day you removed. Move them first.')
    for key, value in body.model_dump().items():
        setattr(slot, key, value)
    commit(db)
    return slot_view(slot)


@router.delete('/slots/{slot_id}')
def delete_slot(slot_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    slot = get_slot(db, ctx, slot_id, lock=True)
    if scoped(db, TimetableEntry, ctx).filter_by(slot_id=slot.id).first():
        raise HTTPException(409, 'Lessons are placed in this period. Remove them first.')
    db.delete(slot)
    commit(db)
    return {'message': 'Removed'}


# --- Teacher availability ------------------------------------------------------------

class AwayInput(Input):
    teacher_id: uuid.UUID
    weekday: int = Weekday
    start_time: time
    end_time: time
    reason: str = Field(default='', max_length=200)

    @model_validator(mode='after')
    def valid(self):
        if self.end_time <= self.start_time:
            raise ValueError('The end time must be after the start time')
        return self


def teacher_row(db, ctx, teacher_id):
    active_teacher(db, teacher_id, ctx)
    return db.get(User, teacher_id)


@router.post('/terms/{period_id}/unavailability', status_code=201)
def add_unavailability(period_id: uuid.UUID, body: AwayInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    get_period(db, ctx, period_id)
    teacher_row(db, ctx, body.teacher_id)
    row = TeacherUnavailability(institution_id=ctx.institution_id, period_id=period_id, **body.model_dump())
    db.add(row)
    commit(db)
    # Lessons already placed in this time are reported so they can be moved.
    affected = [lesson_label(db, ctx, e, s) for e, s in scoped(db, TimetableEntry, ctx).join(TimetableSlot, TimetableSlot.id == TimetableEntry.slot_id).filter(
        TimetableSlot.institution_id == ctx.institution_id, TimetableEntry.period_id == period_id, TimetableEntry.teacher_id == body.teacher_id,
        TimetableEntry.weekday == body.weekday).with_entities(TimetableEntry, TimetableSlot).all()
        if overlaps(s.start_time, s.end_time, body.start_time, body.end_time)]
    return dict(id=row.id, affected_lessons=affected)


@router.delete('/unavailability/{unavailability_id}')
def delete_unavailability(unavailability_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = scoped(db, TeacherUnavailability, ctx).filter_by(id=unavailability_id).first()
    if not row:
        missing()
    db.delete(row)
    commit(db)
    return {'message': 'Removed'}


# --- Lessons ---------------------------------------------------------------------------

def lesson_label(db, ctx, entry, slot):
    subject = scoped(db, Subject, ctx).filter_by(id=entry.subject_id).first()
    group = scoped(db, AcademicClass, ctx).filter_by(id=entry.class_id).first()
    return f"{DAYS[entry.weekday]} {slot.label} ({hm(slot.start_time)}-{hm(slot.end_time)}): {subject.name if subject else 'Lesson'}, {group.name if group else ''}".strip(', ')


def weekly_clashes(db, ctx, period_id, weekday, start, end, *, teacher_id, subject, exclude=None):
    """Clashes for a weekly lesson at this time: teacher double-booked, class double-booked, teacher unavailable."""
    found = []
    rows = scoped(db, TimetableEntry, ctx).join(TimetableSlot, TimetableSlot.id == TimetableEntry.slot_id).join(
        Subject, Subject.id == TimetableEntry.subject_id).filter(
        TimetableSlot.institution_id == ctx.institution_id, Subject.institution_id == ctx.institution_id,
        TimetableEntry.period_id == period_id, TimetableEntry.weekday == weekday,
        or_(TimetableEntry.teacher_id == teacher_id, TimetableEntry.class_id == subject.class_id)
    ).with_entities(TimetableEntry, TimetableSlot, Subject).all()
    for entry, slot, other in rows:
        if entry.id == exclude or not overlaps(start, end, slot.start_time, slot.end_time):
            continue
        if entry.teacher_id == teacher_id:
            found.append(dict(kind='TEACHER', entry_id=str(entry.id), message=f'The teacher already has {lesson_label(db, ctx, entry, slot)}'))
        # Optional offerings (individual registration) may share a class's time, e.g. electives.
        elif entry.class_id == subject.class_id and 'COHORT' in {other.registration_mode, subject.registration_mode}:
            found.append(dict(kind='CLASS', entry_id=str(entry.id), message=f'The class already has {lesson_label(db, ctx, entry, slot)}'))
    for away in scoped(db, TeacherUnavailability, ctx).filter_by(period_id=period_id, teacher_id=teacher_id, weekday=weekday).all():
        if overlaps(start, end, away.start_time, away.end_time):
            found.append(dict(kind='UNAVAILABLE', message=f'The teacher is unavailable {hm(away.start_time)}-{hm(away.end_time)}' + (f' ({away.reason})' if away.reason else '')))
    return found


def offering_teachers(db, ctx, subject):
    ids = {subject.teacher_id} | {u for (u,) in scoped(db, OfferingTeacher, ctx).filter_by(subject_id=subject.id).with_entities(OfferingTeacher.user_id).all()}
    return ids


class EntryInput(Input):
    slot_id: uuid.UUID
    weekday: int = Weekday
    subject_id: uuid.UUID
    teacher_id: uuid.UUID | None = None
    override_reason: str | None = Field(default=None, min_length=5, max_length=300)


def place(db, ctx, period_id, body, entry=None):
    term = get_term(db, ctx, period_id, create=True, lock=True)
    slot = get_slot(db, ctx, body.slot_id)
    if slot.period_id != period_id:
        missing()
    if slot.is_break:
        raise HTTPException(409, 'Lessons cannot be placed in a break')
    if body.weekday not in term.weekdays or not slot_runs(slot, body.weekday, term.weekdays):
        raise HTTPException(409, f'{slot.label} does not run on {DAYS[body.weekday]}')
    subject = scoped(db, Subject, ctx).filter_by(id=body.subject_id).first()
    if not subject:
        missing()
    period = get_period(db, ctx, period_id)
    if subject.class_id not in {c.id for c in open_classes(db, ctx, period)} or (subject.period_id and subject.period_id != period_id):
        raise HTTPException(409, 'This offering does not run in this term')
    teacher_id = body.teacher_id or subject.teacher_id
    if teacher_id not in offering_teachers(db, ctx, subject):
        raise HTTPException(409, 'Choose a teacher allocated to this offering')
    teacher_row(db, ctx, teacher_id)
    clashes = weekly_clashes(db, ctx, period_id, body.weekday, slot.start_time, slot.end_time, teacher_id=teacher_id, subject=subject,
                             exclude=entry.id if entry else None)
    if clashes and not body.override_reason:
        clash_error(clashes)
    if entry is None:
        if scoped(db, TimetableEntry, ctx).filter_by(slot_id=slot.id, weekday=body.weekday, subject_id=subject.id).first():
            raise HTTPException(409, 'This lesson is already in the timetable')
        entry = TimetableEntry(institution_id=ctx.institution_id, period_id=period_id)
        db.add(entry)
    entry.slot_id, entry.weekday, entry.subject_id, entry.class_id, entry.teacher_id = slot.id, body.weekday, subject.id, subject.class_id, teacher_id
    entry.override_reason = body.override_reason if clashes else None
    if clashes:
        record_audit(db, ctx, 'timetable.clash_overridden', subject.id, ctx.institution_id, f'{len(clashes)} clash(es): {body.override_reason}')
    commit(db)
    return dict(id=entry.id, clashes=clashes)


@router.post('/terms/{period_id}/entries', status_code=201)
def add_entry(period_id: uuid.UUID, body: EntryInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    return place(db, ctx, period_id, body)


def get_entry(db, ctx, entry_id, lock=False):
    q = scoped(db, TimetableEntry, ctx).filter_by(id=entry_id)
    entry = (q.with_for_update() if lock else q).first()
    if not entry:
        missing()
    return entry


@router.put('/entries/{entry_id}')
def edit_entry(entry_id: uuid.UUID, body: EntryInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    entry = get_entry(db, ctx, entry_id, lock=True)
    return place(db, ctx, entry.period_id, body, entry)


@router.delete('/entries/{entry_id}')
def delete_entry(entry_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    entry = get_entry(db, ctx, entry_id, lock=True)
    db.delete(entry)
    commit(db)
    return {'message': 'Lesson removed'}


# --- Reading a class timetable ----------------------------------------------------------

def class_access(db, ctx, class_id):
    """Admins, the class teacher, teachers of the class and its students may read it."""
    group = scoped(db, AcademicClass, ctx).filter_by(id=class_id).first()
    if not group:
        missing()
    if ctx.role == UserRole.INSTITUTION_ADMIN:
        return group, None
    if ctx.role == UserRole.TEACHER:
        active_teacher(db, ctx.user_id, ctx)
        teaches = scoped(db, Subject, ctx).filter(Subject.class_id == class_id, Subject.id.in_(taught_subject_ids(db, ctx))).first()
        if group.supervisor_id == ctx.user_id or teaches:
            return group, None
    if ctx.role == UserRole.STUDENT:
        student = scoped(db, Student, ctx).filter_by(user_id=ctx.user_id).first()
        if student and scoped(db, Enrollment, ctx).filter_by(student_id=student.id, class_id=class_id, active=True).first():
            return group, student
    missing()


def entry_rows(db, ctx, filters):
    rows = scoped(db, TimetableEntry, ctx).join(TimetableSlot, TimetableSlot.id == TimetableEntry.slot_id).join(
        Subject, Subject.id == TimetableEntry.subject_id).join(AcademicClass, AcademicClass.id == TimetableEntry.class_id).join(
        User, User.id == TimetableEntry.teacher_id).filter(
        TimetableSlot.institution_id == ctx.institution_id, Subject.institution_id == ctx.institution_id,
        AcademicClass.institution_id == ctx.institution_id, User.institution_id == ctx.institution_id, *filters
    ).with_entities(TimetableEntry, TimetableSlot, Subject, AcademicClass, User).all()
    return rows


def entry_view(entry, slot, subject, group, teacher):
    return dict(id=entry.id, period_id=entry.period_id, slot_id=slot.id, weekday=entry.weekday, start_time=hm(slot.start_time),
                end_time=hm(slot.end_time), slot_label=slot.label, subject_id=subject.id, subject_name=subject.name,
                class_id=group.id, class_name=f"{group.name}{' ' + group.stream if group.stream else ''}",
                teacher_id=teacher.id, teacher_name=name(teacher), override_reason=entry.override_reason)


def student_subject_ids(db, ctx, student, class_id):
    registered = scoped(db, CourseRegistration, ctx).filter_by(student_id=student.id, active=True).with_entities(CourseRegistration.subject_id)
    return scoped(db, Subject, ctx).filter(Subject.class_id == class_id, or_(Subject.registration_mode == 'COHORT', Subject.id.in_(registered))).with_entities(Subject.id)


def default_period(db, ctx):
    """The published term running today, else the next one, else the most recent."""
    rows = scoped(db, TimetableTerm, ctx).join(AcademicPeriod, AcademicPeriod.id == TimetableTerm.period_id).filter(
        AcademicPeriod.institution_id == ctx.institution_id, TimetableTerm.published_at.is_not(None)
    ).with_entities(AcademicPeriod).order_by(AcademicPeriod.start_date).all()
    today = date.today()
    pick = next((p for p in rows if p.start_date <= today <= p.end_date), None) or next((p for p in rows if p.start_date > today), None)
    pick = pick or (rows[-1] if rows else None)
    if pick is None:
        raise HTTPException(404, 'No timetable has been published yet')
    return pick.id


@router.get('/classes/{class_id}')
def class_timetable(class_id: uuid.UUID, period_id: uuid.UUID | None = None, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    group, student = class_access(db, ctx, class_id)
    period_id = period_id or default_period(db, ctx)
    term = get_term(db, ctx, period_id)
    if ctx.role != UserRole.INSTITUTION_ADMIN and not (term and term.published_at):
        raise HTTPException(404, 'This timetable has not been published yet')
    filters = [TimetableEntry.period_id == period_id, TimetableEntry.class_id == class_id]
    if student is not None:
        filters.append(TimetableEntry.subject_id.in_(student_subject_ids(db, ctx, student, class_id)))
    entries = [entry_view(*row) for row in entry_rows(db, ctx, filters)]
    slots = scoped(db, TimetableSlot, ctx).filter_by(period_id=period_id).order_by(TimetableSlot.start_time).all()
    period = get_period(db, ctx, period_id)
    out = dict(period_id=period.id, period_name=period.name, class_id=group.id, class_name=f"{group.name}{' ' + group.stream if group.stream else ''}", weekdays=term.weekdays if term else [1, 2, 3, 4, 5],
               published=bool(term and term.published_at), slots=[slot_view(s) for s in slots], entries=entries)
    if ctx.role == UserRole.INSTITUTION_ADMIN:
        subjects = scoped(db, Subject, ctx).filter(Subject.class_id == class_id).order_by(Subject.name).all()
        subjects = [s for s in subjects if not s.period_id or s.period_id == period.id]
        teacher_ids = {s.id: offering_teachers(db, ctx, s) for s in subjects}
        users = {u.id: u for u in db.query(User).filter(User.institution_id == ctx.institution_id,
                                                         User.id.in_(set().union(*teacher_ids.values()) or {uuid.uuid4()})).all()}
        out['subjects'] = [dict(id=s.id, name=s.name, lead_teacher_id=s.teacher_id, optional=s.registration_mode == 'INDIVIDUAL',
                                teachers=[dict(id=t, name=name(users.get(t))) for t in teacher_ids[s.id] if t in users]) for s in subjects]
    return out


@router.get('/teachers/{teacher_id}')
def teacher_timetable(teacher_id: uuid.UUID, period_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    teacher_row(db, ctx, teacher_id)
    get_period(db, ctx, period_id)
    return [entry_view(*row) for row in entry_rows(db, ctx, [TimetableEntry.period_id == period_id, TimetableEntry.teacher_id == teacher_id])]


# --- One-day lesson changes ---------------------------------------------------------------

class ChangeInput(Input):
    lesson_date: date
    kind: Literal['CANCELLED', 'MOVED', 'SUBSTITUTE']
    substitute_id: uuid.UUID | None = None
    new_date: date | None = None
    new_slot_id: uuid.UUID | None = None
    note: str = Field(default='', max_length=300)
    override_reason: str | None = Field(default=None, min_length=5, max_length=300)

    @model_validator(mode='after')
    def fields_for_kind(self):
        if self.kind == 'SUBSTITUTE' and not self.substitute_id:
            raise ValueError('Choose the substitute teacher')
        if self.kind == 'MOVED' and not (self.new_date and self.new_slot_id):
            raise ValueError('Choose the new date and lesson period')
        if self.kind != 'SUBSTITUTE':
            self.substitute_id = None
        if self.kind != 'MOVED':
            self.new_date, self.new_slot_id = None, None
        return self


def term_for_date(db, ctx, day):
    return scoped(db, AcademicPeriod, ctx).filter(AcademicPeriod.start_date <= day, AcademicPeriod.end_date >= day).first()


def day_clashes(db, ctx, day, start, end, *, teacher_id, subject, exclude_entry):
    """Clashes on one date, counting that day's changes as well as the weekly timetable."""
    period = term_for_date(db, ctx, day)
    found = []
    if period is not None:
        weekly = weekly_clashes(db, ctx, period.id, day.isoweekday(), start, end, teacher_id=teacher_id, subject=subject, exclude=exclude_entry)
        # Lessons cancelled or moved away that day no longer clash.
        gone = {str(c.entry_id) for c in scoped(db, LessonChange, ctx).filter(LessonChange.lesson_date == day, LessonChange.kind.in_(['CANCELLED', 'MOVED'])).all()}
        found = [c for c in weekly if c.get('entry_id') not in gone]
    for change, entry, slot in scoped(db, LessonChange, ctx).join(TimetableEntry, TimetableEntry.id == LessonChange.entry_id).join(
            TimetableSlot, TimetableSlot.id == LessonChange.new_slot_id).filter(
            TimetableEntry.institution_id == ctx.institution_id, LessonChange.kind == 'MOVED', LessonChange.new_date == day,
            or_(TimetableEntry.teacher_id == teacher_id, TimetableEntry.class_id == subject.class_id)).with_entities(LessonChange, TimetableEntry, TimetableSlot).all():
        if entry.id != exclude_entry and overlaps(start, end, slot.start_time, slot.end_time):
            found.append(dict(kind='MOVED', message=f'A lesson was moved to this time: {lesson_label(db, ctx, entry, slot)}'))
    for change, entry, slot in scoped(db, LessonChange, ctx).join(TimetableEntry, TimetableEntry.id == LessonChange.entry_id).join(
            TimetableSlot, TimetableSlot.id == TimetableEntry.slot_id).filter(
            TimetableEntry.institution_id == ctx.institution_id, LessonChange.kind == 'SUBSTITUTE', LessonChange.lesson_date == day,
            LessonChange.substitute_id == teacher_id).with_entities(LessonChange, TimetableEntry, TimetableSlot).all():
        if entry.id != exclude_entry and overlaps(start, end, slot.start_time, slot.end_time):
            found.append(dict(kind='TEACHER', message=f'The teacher is already covering {lesson_label(db, ctx, entry, slot)}'))
    return found


def change_view(change, entry=None, slot=None, new_slot=None, names=None):
    names = names or {}
    return dict(id=change.id, entry_id=change.entry_id, lesson_date=change.lesson_date, kind=change.kind,
                substitute_id=change.substitute_id, substitute_name=names.get(change.substitute_id),
                new_date=change.new_date, new_slot_id=change.new_slot_id, new_slot_label=new_slot.label if new_slot else None,
                new_start=hm(new_slot.start_time) if new_slot else None, note=change.note, override_reason=change.override_reason)


@router.post('/entries/{entry_id}/changes', status_code=201)
def add_change(entry_id: uuid.UUID, body: ChangeInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    entry = get_entry(db, ctx, entry_id, lock=True)
    period = get_period(db, ctx, entry.period_id)
    if not (period.start_date <= body.lesson_date <= period.end_date) or body.lesson_date.isoweekday() != entry.weekday:
        raise HTTPException(409, f'This lesson runs on {DAYS[entry.weekday]}s in {period.name}. Choose one of those dates.')
    if scoped(db, LessonChange, ctx).filter_by(entry_id=entry.id, lesson_date=body.lesson_date).first():
        raise HTTPException(409, 'This lesson already has a change on that date. Remove it first.')
    subject = scoped(db, Subject, ctx).filter_by(id=entry.subject_id).one()
    slot = get_slot(db, ctx, entry.slot_id)
    clashes = []
    if body.kind == 'SUBSTITUTE':
        if body.substitute_id == entry.teacher_id:
            raise HTTPException(409, 'Choose someone other than the usual teacher')
        teacher_row(db, ctx, body.substitute_id)
        clashes = [c for c in day_clashes(db, ctx, body.lesson_date, slot.start_time, slot.end_time, teacher_id=body.substitute_id,
                                          subject=subject, exclude_entry=entry.id) if c['kind'] != 'CLASS']
    elif body.kind == 'MOVED':
        new_slot = get_slot(db, ctx, body.new_slot_id)
        target = term_for_date(db, ctx, body.new_date)
        term = get_term(db, ctx, new_slot.period_id)
        days = term.weekdays if term else [1, 2, 3, 4, 5]
        if new_slot.is_break or target is None or target.id != new_slot.period_id or not slot_runs(new_slot, body.new_date.isoweekday(), days):
            raise HTTPException(409, 'Choose a lesson period that runs on the new date')
        if (body.new_date, new_slot.id) == (body.lesson_date, slot.id):
            raise HTTPException(409, 'The new time is the same as the usual time')
        clashes = day_clashes(db, ctx, body.new_date, new_slot.start_time, new_slot.end_time, teacher_id=entry.teacher_id, subject=subject, exclude_entry=entry.id)
    if clashes and not body.override_reason:
        clash_error(clashes)
    change = LessonChange(institution_id=ctx.institution_id, entry_id=entry.id, created_by=ctx.actor_user_id or ctx.user_id,
                          **body.model_dump(exclude={'override_reason'}), override_reason=body.override_reason if clashes else None)
    db.add(change)
    record_audit(db, ctx, f'timetable.lesson_{body.kind.lower()}', entry.id, ctx.institution_id, f'{body.lesson_date}' + (f'; override: {body.override_reason}' if clashes else ''))
    commit(db)
    return dict(id=change.id, clashes=clashes)


@router.delete('/changes/{change_id}')
def delete_change(change_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    change = scoped(db, LessonChange, ctx).filter_by(id=change_id).first()
    if not change:
        missing()
    record_audit(db, ctx, 'timetable.change_removed', change.entry_id, ctx.institution_id, str(change.lesson_date))
    db.delete(change)
    commit(db)
    return {'message': 'Change removed'}


@router.get('/changes')
def changes(start: date, end: date, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    if end < start or (end - start).days > 120:
        raise HTTPException(422, 'Choose a range of at most 120 days')
    rows = scoped(db, LessonChange, ctx).filter(or_(LessonChange.lesson_date.between(start, end), LessonChange.new_date.between(start, end))).order_by(
        LessonChange.lesson_date).all()
    entries = {e['id']: e for e in (entry_view(*r) for r in entry_rows(db, ctx, [TimetableEntry.id.in_({c.entry_id for c in rows} or {uuid.uuid4()})]))}
    slots = {s.id: s for s in scoped(db, TimetableSlot, ctx).filter(TimetableSlot.id.in_({c.new_slot_id for c in rows if c.new_slot_id} or {uuid.uuid4()})).all()}
    names = {u.id: name(u) for u in db.query(User).filter(User.institution_id == ctx.institution_id,
                                                          User.id.in_({c.substitute_id for c in rows if c.substitute_id} or {uuid.uuid4()})).all()}
    return [dict(change_view(c, new_slot=slots.get(c.new_slot_id), names=names), lesson=entries.get(c.entry_id)) for c in rows]


# --- My timetable ---------------------------------------------------------------------------

def published_terms(db, ctx, start, end):
    rows = scoped(db, TimetableTerm, ctx).join(AcademicPeriod, AcademicPeriod.id == TimetableTerm.period_id).filter(
        AcademicPeriod.institution_id == ctx.institution_id, TimetableTerm.published_at.is_not(None),
        AcademicPeriod.start_date <= end, AcademicPeriod.end_date >= start).with_entities(TimetableTerm, AcademicPeriod).all()
    return rows


def lessons(db, ctx, start, end, filters, substitute_for=None):
    """Lessons on each date in [start, end] for the given weekly-entry filters, with that day's changes applied."""
    terms = published_terms(db, ctx, start, end)
    if not terms:
        return []
    periods = {p.id: (t, p) for t, p in terms}
    rows = entry_rows(db, ctx, [TimetableEntry.period_id.in_(list(periods)), *filters])
    by_entry = {r[0].id: r for r in rows}
    sub_changes = []
    if substitute_for is not None:
        sub_changes = scoped(db, LessonChange, ctx).filter(LessonChange.kind == 'SUBSTITUTE', LessonChange.substitute_id == substitute_for,
                                                           LessonChange.lesson_date.between(start, end)).all()
        missing_ids = {c.entry_id for c in sub_changes} - set(by_entry)
        if missing_ids:
            for r in entry_rows(db, ctx, [TimetableEntry.id.in_(missing_ids)]):
                by_entry[r[0].id] = r
    ids = set(by_entry) or {uuid.uuid4()}
    day_changes = scoped(db, LessonChange, ctx).filter(LessonChange.entry_id.in_(ids), or_(
        LessonChange.lesson_date.between(start, end), LessonChange.new_date.between(start, end))).all()
    on = {(c.entry_id, c.lesson_date): c for c in day_changes}
    new_slots = {s.id: s for s in scoped(db, TimetableSlot, ctx).filter(TimetableSlot.id.in_({c.new_slot_id for c in day_changes if c.new_slot_id} or {uuid.uuid4()})).all()}
    names = {u.id: name(u) for u in db.query(User).filter(User.institution_id == ctx.institution_id,
                                                          User.id.in_({c.substitute_id for c in day_changes if c.substitute_id} or {uuid.uuid4()})).all()}
    out = []

    def add(day, row, status, change=None, slot=None):
        entry, base_slot, subject, group, teacher = row
        view = entry_view(entry, slot or base_slot, subject, group, teacher)
        view.update(date=day, status=status, note=change.note if change else '', change_id=change.id if change else None,
                    substitute_name=names.get(change.substitute_id) if change else None)
        out.append(view)

    day = start
    while day <= end:
        for term, period in periods.values():
            if not (period.start_date <= day <= period.end_date) or day.isoweekday() not in term.weekdays:
                continue
            for entry_id, row in by_entry.items():
                entry, slot = row[0], row[1]
                if entry.period_id != period.id or entry.weekday != day.isoweekday() or not slot_runs(slot, entry.weekday, term.weekdays):
                    continue
                change = on.get((entry_id, day))
                covering = change is not None and change.kind == 'SUBSTITUTE' and change.substitute_id == substitute_for
                # Teachers see their own lessons and the ones they cover; students see all of theirs.
                if substitute_for is not None and entry.teacher_id != substitute_for and not covering:
                    continue
                if change is None:
                    add(day, row, 'SCHEDULED')
                elif change.kind == 'CANCELLED':
                    add(day, row, 'CANCELLED', change)
                elif change.kind == 'MOVED':
                    add(day, row, 'MOVED_AWAY', change)
                elif covering:
                    add(day, row, 'COVERING', change)
                else:
                    add(day, row, 'SUBSTITUTE', change)
        day += timedelta(days=1)
    for change in day_changes:
        if change.kind == 'MOVED' and start <= change.new_date <= end and change.entry_id in by_entry:
            row = by_entry[change.entry_id]
            if substitute_for is not None and row[0].teacher_id != substitute_for:
                continue
            add(change.new_date, row, 'MOVED_IN', change, new_slots.get(change.new_slot_id))
    out.sort(key=lambda lesson: (lesson['date'], lesson['start_time'], lesson['class_name']))
    return out


@router.get('/me')
def my_timetable(start: date | None = None, days: int = Query(7, ge=1, le=42), db: Session = Depends(get_db),
                 ctx: AuthContext = Depends(require_role(UserRole.TEACHER, UserRole.STUDENT))):
    start = start or date.today()
    end = start + timedelta(days=days - 1)
    if ctx.role == UserRole.TEACHER:
        active_teacher(db, ctx.user_id, ctx)
        result = lessons(db, ctx, start, end, [TimetableEntry.teacher_id == ctx.user_id], substitute_for=ctx.user_id)
    else:
        student = scoped(db, Student, ctx).filter_by(user_id=ctx.user_id).first()
        if not student:
            return dict(start=start, end=end, lessons=[])
        classes = scoped(db, Enrollment, ctx).filter_by(student_id=student.id, active=True).with_entities(Enrollment.class_id)
        registered = scoped(db, CourseRegistration, ctx).filter_by(student_id=student.id, active=True).with_entities(CourseRegistration.subject_id)
        mine = scoped(db, Subject, ctx).filter(Subject.class_id.in_(classes), or_(Subject.registration_mode == 'COHORT', Subject.id.in_(registered))).with_entities(Subject.id)
        result = lessons(db, ctx, start, end, [TimetableEntry.subject_id.in_(mine)])
    return dict(start=start, end=end, lessons=result)
