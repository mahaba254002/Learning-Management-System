"""Course registration windows: students choose optional units, staff approve them."""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.routes.learning import as_utc, own_student
from app.api.routes.teaching import admin, commit, missing
from app.core.deps import AuthContext, require_role
from app.core.permissions import require_permission
from app.core.tenancy import owned, scoped
from app.db.session import get_db
from app.models.academic import AcademicClass, Enrollment, Score, Coursework, Student, Subject
from app.models.curriculum import CatalogueUnit, CourseRegistration
from app.models.elearning import RegistrationWindow
from app.models.pilot import AcademicPeriod
from app.models.user import User, UserRole
from app.schemas.academic import Input
from app.services.audit_service import record_audit
from app.services.elearning import notify
from app.services.quiz import now

router = APIRouter(prefix='/api', tags=['Course registration'])
approver = require_permission('registrations.approve')
student_role = require_role(UserRole.STUDENT)


class WindowInput(Input):
    title: str = Field(min_length=1, max_length=120)
    period_id: uuid.UUID | None = None
    opens_at: AwareDatetime
    closes_at: AwareDatetime
    min_units: int = Field(default=0, ge=0, le=50)
    max_units: int = Field(ge=1, le=50)
    min_credits: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=6, decimal_places=2)
    max_credits: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=6, decimal_places=2)
    class_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)

    @model_validator(mode='after')
    def valid(self):
        if self.closes_at <= self.opens_at:
            raise ValueError('The window must close after it opens')
        if self.max_units < self.min_units:
            raise ValueError('The maximum number of units must be at least the minimum')
        if self.min_credits is not None and self.max_credits is not None and self.max_credits < self.min_credits:
            raise ValueError('The maximum credits must be at least the minimum')
        return self


class ChoicesInput(Input):
    subject_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class DecisionInput(Input):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    approve: bool
    note: str = Field(default='', max_length=300)

    @model_validator(mode='after')
    def reason_for_refusal(self):
        if not self.approve and len(self.note.strip()) < 3:
            raise ValueError('Give the student a reason when not approving a choice')
        return self


def window_view(w, at=None):
    at = at or now()
    state = 'UPCOMING' if at < as_utc(w.opens_at) else 'CLOSED' if at >= as_utc(w.closes_at) else 'OPEN'
    return dict(id=w.id, title=w.title, period_id=w.period_id, opens_at=as_utc(w.opens_at), closes_at=as_utc(w.closes_at),
                min_units=w.min_units, max_units=w.max_units, min_credits=w.min_credits, max_credits=w.max_credits,
                class_ids=w.class_ids, state=state)


def window_values(db, ctx, body):
    owned(db, AcademicPeriod, body.period_id, ctx.institution_id)
    if body.class_ids and scoped(db, AcademicClass, ctx).filter(AcademicClass.id.in_(body.class_ids)).count() != len(set(body.class_ids)):
        missing()
    return dict(body.model_dump(exclude={'class_ids'}), class_ids=[str(i) for i in dict.fromkeys(body.class_ids)])


@router.get('/course-registration/windows')
def windows(db: Session = Depends(get_db), ctx: AuthContext = Depends(approver)):
    rows = scoped(db, RegistrationWindow, ctx).order_by(RegistrationWindow.opens_at.desc()).all()
    counts = dict(scoped(db, CourseRegistration, ctx).filter(CourseRegistration.status == 'PENDING').with_entities(
        CourseRegistration.window_id, func.count(CourseRegistration.id)).group_by(CourseRegistration.window_id).all())
    return [dict(window_view(w), pending=counts.get(w.id, 0)) for w in rows]


@router.post('/course-registration/windows', status_code=201)
def create_window(body: WindowInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = RegistrationWindow(institution_id=ctx.institution_id, **window_values(db, ctx, body))
    db.add(row)
    db.flush()
    record_audit(db, ctx, 'registration.window_created', row.id, ctx.institution_id, body.title)
    commit(db)
    return window_view(row)


@router.put('/course-registration/windows/{window_id}')
def update_window(window_id: uuid.UUID, body: WindowInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = owned(db, RegistrationWindow, window_id, ctx.institution_id, lock=True)
    for key, value in window_values(db, ctx, body).items():
        setattr(row, key, value)
    record_audit(db, ctx, 'registration.window_changed', row.id, ctx.institution_id, body.title)
    commit(db)
    return window_view(row)


def credits_of(db, subjects):
    ids = [s.catalogue_id for s in subjects if s.catalogue_id]
    units = {u.id: u.credits for u in db.query(CatalogueUnit).filter(CatalogueUnit.id.in_(ids)).all()} if ids else {}
    return {s.id: units.get(s.catalogue_id) for s in subjects}


def windows_for(db, ctx, student, at):
    classes = [c for (c,) in scoped(db, Enrollment, ctx).filter_by(student_id=student.id, active=True).with_entities(Enrollment.class_id).all()]
    rows = scoped(db, RegistrationWindow, ctx).all()
    return [w for w in rows if not w.class_ids or set(w.class_ids) & {str(c) for c in classes}], classes


def offered(db, ctx, window, classes):
    allowed = [c for c in classes if not window.class_ids or str(c) in window.class_ids]
    q = scoped(db, Subject, ctx).filter(Subject.class_id.in_(allowed), Subject.registration_mode == 'INDIVIDUAL')
    if window.period_id:
        q = q.filter(Subject.period_id == window.period_id)
    return q.order_by(Subject.name).all()


@router.get('/student/registration')
def my_registration(db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    student = own_student(db, ctx)
    at = now()
    rows, classes = windows_for(db, ctx, student, at)
    mine = {r.subject_id: r for r in scoped(db, CourseRegistration, ctx).filter_by(student_id=student.id).all()}
    out = []
    for w in sorted(rows, key=lambda w: as_utc(w.opens_at), reverse=True):
        view = window_view(w, at)
        if view['state'] == 'CLOSED' and not any(r.window_id == w.id for r in mine.values()):
            continue
        units = offered(db, ctx, w, classes)
        credits = credits_of(db, units)
        teachers = {u.id: f'{u.first_name} {u.last_name}' for u in scoped(db, User, ctx).filter(User.id.in_([s.teacher_id for s in units])).all()}
        view['units'] = [dict(id=s.id, name=s.name, credits=credits[s.id], teacher_name=teachers.get(s.teacher_id, ''),
                              status=mine[s.id].status if s.id in mine else None,
                              note=mine[s.id].decision_note if s.id in mine else '') for s in units]
        out.append(view)
    return out


@router.put('/student/registration/{window_id}')
def choose(window_id: uuid.UUID, body: ChoicesInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    from app.services.progression import course_check, lock_entry
    lock_entry(db, ctx.institution_id)
    student = own_student(db, ctx)
    at = now()
    rows, classes = windows_for(db, ctx, student, at)
    window = next((w for w in rows if w.id == window_id), None)
    if window is None:
        missing()
    if window_view(window, at)['state'] != 'OPEN':
        raise HTTPException(409, 'This registration window is not open')
    units = {s.id: s for s in offered(db, ctx, window, classes)}
    chosen = list(dict.fromkeys(body.subject_ids))
    if not set(chosen) <= set(units):
        missing()
    if not window.min_units <= len(chosen) <= window.max_units:
        raise HTTPException(422, f'Choose between {window.min_units} and {window.max_units} units')
    credits = credits_of(db, list(units.values()))
    total = sum((credits[i] or Decimal(0) for i in chosen), Decimal(0))
    if window.min_credits is not None and total < window.min_credits or window.max_credits is not None and total > window.max_credits:
        limits = f"at least {window.min_credits:g}" if window.max_credits is None else f"between {window.min_credits or 0:g} and {window.max_credits:g}"
        raise HTTPException(422, f'Your choices add up to {total:g} credits. Choose {limits} credits.')
    existing = {r.subject_id: r for r in scoped(db, CourseRegistration, ctx).filter(
        CourseRegistration.student_id == student.id, CourseRegistration.subject_id.in_(units)).with_for_update().all()}
    problems = []
    for subject_id in chosen:
        row = existing.get(subject_id)
        if row is not None and row.status in {'APPROVED', 'PENDING'}:
            continue
        issues = course_check(db, ctx.institution_id, student.id, units[subject_id])
        if issues:
            problems.append(f"{units[subject_id].name}: {'; '.join(issues)}")
    if problems:
        raise HTTPException(409, 'You cannot choose: ' + ' | '.join(problems))
    for subject_id, row in existing.items():
        if subject_id in chosen or row.status not in {'APPROVED', 'PENDING'}:
            continue
        if row.status == 'APPROVED':
            marked = scoped(db, Score, ctx).join(Coursework, Coursework.id == Score.coursework_id).filter(
                Coursework.subject_id == subject_id, Score.student_id == student.id).first()
            if marked:
                raise HTTPException(409, f'You already have marks in {units[subject_id].name}. Ask the office to drop it.')
        row.status, row.active, row.window_id = 'DROPPED', False, window.id
    for subject_id in chosen:
        row = existing.get(subject_id)
        if row is None:
            row = CourseRegistration(institution_id=ctx.institution_id, subject_id=subject_id, student_id=student.id)
            db.add(row)
        elif row.status in {'APPROVED', 'PENDING'}:
            continue
        row.status, row.active, row.window_id = 'PENDING', False, window.id
        row.decided_by, row.decided_at, row.decision_note = None, None, ''
    record_audit(db, ctx, 'registration.choices_saved', window.id, ctx.institution_id, f'{len(chosen)} units')
    commit(db)
    return my_registration(db, ctx)


@router.get('/course-registration/requests')
def requests(window_id: uuid.UUID | None = None, status: str = 'PENDING', db: Session = Depends(get_db), ctx: AuthContext = Depends(approver)):
    if status not in {'PENDING', 'APPROVED', 'REJECTED', 'DROPPED'}:
        raise HTTPException(422, 'Unknown status')
    q = scoped(db, CourseRegistration, ctx).filter(CourseRegistration.status == status, CourseRegistration.window_id.isnot(None))
    if window_id:
        q = q.filter(CourseRegistration.window_id == window_id)
    rows = q.join(Subject, Subject.id == CourseRegistration.subject_id).join(Student, Student.id == CourseRegistration.student_id).join(
        User, User.id == Student.user_id).join(AcademicClass, AcademicClass.id == Subject.class_id).filter(
        Subject.institution_id == ctx.institution_id, Student.institution_id == ctx.institution_id).with_entities(
        CourseRegistration, Subject, Student, User, AcademicClass).order_by(User.first_name, User.last_name, Subject.name).limit(1000).all()
    credits = credits_of(db, [s for _, s, _, _, _ in rows])
    return [dict(id=r.id, window_id=r.window_id, status=r.status, requested_at=as_utc(r.updated_at), note=r.decision_note,
                 subject_id=s.id, subject_name=s.name, credits=credits[s.id], class_name=c.name,
                 student_id=st.id, student_name=f'{u.first_name} {u.last_name}', admission_number=st.admission_number)
            for r, s, st, u, c in rows]


@router.post('/course-registration/decisions')
def decide(body: DecisionInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(approver)):
    from app.services.progression import course_check, lock_entry
    lock_entry(db, ctx.institution_id)
    rows = scoped(db, CourseRegistration, ctx).filter(CourseRegistration.id.in_(body.ids), CourseRegistration.status == 'PENDING').with_for_update().all()
    if len(rows) != len(set(body.ids)):
        raise HTTPException(409, 'Some choices were already decided or changed. Reload the list.')
    at, skipped = now(), []
    subjects = {s.id: s for s in scoped(db, Subject, ctx).filter(Subject.id.in_([r.subject_id for r in rows])).all()}
    users = dict(scoped(db, Student, ctx).filter(Student.id.in_([r.student_id for r in rows])).with_entities(Student.id, Student.user_id).all())
    for row in rows:
        subject = subjects[row.subject_id]
        if body.approve:
            issues = course_check(db, ctx.institution_id, row.student_id, subject)
            if issues:
                skipped.append(dict(id=row.id, reason='; '.join(issues)))
                continue
        row.status = 'APPROVED' if body.approve else 'REJECTED'
        row.active = body.approve
        row.decided_by, row.decided_at, row.decision_note = ctx.user_id, at, body.note.strip()
        verdict = 'approved' if body.approve else 'not approved'
        notify(db, ctx.institution_id, [users[row.student_id]], f'registration:{row.id}:{int(at.timestamp())}',
               f'{subject.name} {verdict}', body.note.strip(), '/student/registration')
    record_audit(db, ctx, 'registration.decided', rows[0].window_id if rows else None, ctx.institution_id,
                 f"{'approved' if body.approve else 'rejected'} {len(rows) - len(skipped)}; skipped {len(skipped)}")
    commit(db)
    return dict(decided=len(rows) - len(skipped), skipped=skipped)
