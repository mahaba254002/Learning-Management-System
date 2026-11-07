"""Student records: status, guardians, fee status, discipline, announcements and attendance summaries.

Who sees what:
- Institution admins: everything.
- Class teachers (class supervisors): students in the classes they supervise. They see
  guardians and fee status, and keep discipline records. They cannot change fees.
- Non-teaching staff: student details and guardians with students.view; fee status
  with fees.manage.
"""
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.routes.teaching import active_teacher, commit, get_class, missing, taught_subject_ids
from app.core.deps import AuthContext, require_role, require_tenant_user
from app.core.permissions import granted_permissions
from app.core.tenancy import scoped
from app.db.session import get_db
from app.models.academic import AcademicClass, Enrollment, Student, Subject
from app.models.pilot import AcademicPeriod, AcademicYear, AuthSession
from app.models.records import Announcement, DisciplineRecord, FeeStatus, Guardian, StudentGuardian
from app.models.user import User, UserRole, UserStatus
from app.schemas.academic import Input
from app.services import attendance as attendance_service
from app.services.audit_service import record_audit

router = APIRouter(prefix="/api", tags=["Student records"])
admin_only = require_role(UserRole.INSTITUTION_ADMIN)
PAGE = 50


# --- Access -------------------------------------------------------------------

class Access:
    def __init__(self, db, ctx):
        self.ctx, self.admin, self.perms, self.classes = ctx, ctx.role == UserRole.INSTITUTION_ADMIN, set(), None
        if self.admin:
            return
        if ctx.role == UserRole.TEACHER:
            active_teacher(db, ctx.user_id, ctx)
            self.classes = [cid for (cid,) in scoped(db, AcademicClass, ctx).filter(AcademicClass.supervisor_id == ctx.user_id).with_entities(AcademicClass.id).all()]
        elif ctx.role == UserRole.STAFF:
            self.perms = granted_permissions(db, ctx.institution_id, ctx.user_id)
        else:
            raise HTTPException(403, "You do not have permission to perform this action")

    @property
    def supervisor(self):
        # A teacher counts as a class teacher only while supervising at least one class.
        return bool(self.classes)

    def can(self, what):
        if self.admin:
            return True
        rules = {
            'students': self.supervisor or 'students.view' in self.perms,
            'guardians': self.supervisor or 'students.view' in self.perms,
            'fees': self.supervisor or 'fees.manage' in self.perms,
            'edit_fees': 'fees.manage' in self.perms,
            'discipline': self.supervisor,
        }
        return rules.get(what, False)

    def need(self, what):
        if not self.can(what):
            raise HTTPException(403, "You do not have permission to perform this action")

    def flags(self):
        return {key: self.can(key) for key in ('students', 'guardians', 'fees', 'edit_fees', 'discipline')} | {
            'edit_status': self.admin, 'edit_guardians': self.admin}


def access(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    return Access(db, ctx)


def student_query(db, acc):
    """Students this person may see. Class teachers only see their classes' current students."""
    ctx = acc.ctx
    q = scoped(db, Student, ctx).join(User, User.id == Student.user_id).filter(
        User.institution_id == ctx.institution_id, User.status != UserStatus.ARCHIVED)
    if acc.supervisor and not acc.admin and 'students.view' not in acc.perms and 'fees.manage' not in acc.perms:
        mine = scoped(db, Enrollment, ctx).filter(Enrollment.class_id.in_(acc.classes or [uuid.uuid4()]), Enrollment.active.is_(True)).with_entities(Enrollment.student_id)
        q = q.filter(Student.id.in_(mine))
    return q


def get_student(db, acc, student_id, *, lock=False):
    q = student_query(db, acc).filter(Student.id == student_id)
    if lock:
        q = q.with_for_update(of=Student)
    found = q.with_entities(Student, User).first()
    if not found:
        missing()
    return found


def like(term):
    return '%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


def current_classes(db, ctx, student_ids):
    if not student_ids:
        return {}
    rows = scoped(db, Enrollment, ctx).join(AcademicClass, AcademicClass.id == Enrollment.class_id).filter(
        AcademicClass.institution_id == ctx.institution_id, Enrollment.active.is_(True), Enrollment.student_id.in_(student_ids)
    ).with_entities(Enrollment.student_id, AcademicClass).all()
    out = {}
    for sid, group in rows:
        out.setdefault(sid, []).append(dict(id=group.id, name=f"{group.name}{' ' + group.stream if group.stream else ''}", academic_year=group.academic_year))
    return out


def student_row(student, user, classes):
    return dict(id=student.id, admission_number=student.admission_number, first_name=user.first_name, last_name=user.last_name,
                status=student.status, left_on=student.left_on, classes=classes.get(student.id, []))


# --- Student list, detail and status ---------------------------------------------

@router.get("/records/students")
def students(search: str = Query('', max_length=100), status: Literal['ACTIVE', 'TRANSFERRED', 'GRADUATED', 'WITHDRAWN', 'ALL'] = 'ACTIVE',
             class_id: uuid.UUID | None = None, offset: int = Query(0, ge=0), db: Session = Depends(get_db), acc: Access = Depends(access)):
    acc.need('students')
    q = student_query(db, acc)
    if status != 'ALL':
        q = q.filter(Student.status == status)
    if class_id:
        q = q.filter(Student.id.in_(scoped(db, Enrollment, acc.ctx).filter(Enrollment.class_id == class_id, Enrollment.active.is_(True)).with_entities(Enrollment.student_id)))
    if search:
        term = like(search)
        q = q.filter(or_(*(c.ilike(term, escape='\\') for c in [Student.admission_number, User.first_name, User.last_name])))
    total = q.count()
    page = q.with_entities(Student, User).order_by(User.first_name, User.last_name, Student.id).offset(offset).limit(PAGE).all()
    classes = current_classes(db, acc.ctx, [s.id for s, _ in page])
    return dict(total=total, items=[student_row(s, u, classes) for s, u in page], can=acc.flags(), classes=visible_classes(db, acc))


def visible_classes(db, acc):
    q = scoped(db, AcademicClass, acc.ctx)
    if acc.supervisor and not acc.admin and not ({'students.view', 'fees.manage'} & acc.perms):
        q = q.filter(AcademicClass.id.in_(acc.classes or [uuid.uuid4()]))
    open_years = db.query(AcademicYear.name).filter(AcademicYear.institution_id == acc.ctx.institution_id, AcademicYear.status != 'CLOSED')
    q = q.filter(or_(AcademicClass.academic_year.in_(open_years), ~AcademicClass.academic_year.in_(
        db.query(AcademicYear.name).filter(AcademicYear.institution_id == acc.ctx.institution_id))))
    return [dict(id=c.id, name=f"{c.name}{' ' + c.stream if c.stream else ''}", academic_year=c.academic_year)
            for c in q.order_by(AcademicClass.academic_year.desc(), AcademicClass.name).all()]


@router.get("/records/students/{student_id}")
def student_detail(student_id: uuid.UUID, db: Session = Depends(get_db), acc: Access = Depends(access)):
    if not (acc.can('students') or acc.can('fees')):
        acc.need('students')
    student, user = get_student(db, acc, student_id)
    ctx = acc.ctx
    out = student_row(student, user, current_classes(db, ctx, [student.id]))
    out.update(status_note=student.status_note, email=user.email, phone=student.phone, can=acc.flags())
    if acc.can('guardians'):
        out['guardians'] = guardian_list(db, ctx, student.id)
    if acc.can('fees'):
        rows = scoped(db, FeeStatus, ctx).join(AcademicPeriod, AcademicPeriod.id == FeeStatus.period_id).filter(
            AcademicPeriod.institution_id == ctx.institution_id, FeeStatus.student_id == student.id
        ).with_entities(FeeStatus, AcademicPeriod).order_by(AcademicPeriod.start_date.desc()).all()
        out['fees'] = [fee_view(f, p) for f, p in rows]
    if acc.can('discipline'):
        out['discipline'] = [discipline_view(r) for r in scoped(db, DisciplineRecord, ctx).filter_by(student_id=student.id).order_by(
            DisciplineRecord.occurred_on.desc(), DisciplineRecord.created_at.desc()).all()]
    return out


class StatusInput(Input):
    status: Literal['ACTIVE', 'TRANSFERRED', 'GRADUATED', 'WITHDRAWN']
    left_on: date | None = None
    note: str = Field(default='', max_length=300)

    @model_validator(mode='after')
    def leaving_date(self):
        if self.status == 'ACTIVE':
            self.left_on = None
        elif self.left_on is None:
            raise ValueError('Give the date the student left')
        elif self.left_on > date.today():
            raise ValueError('The leaving date cannot be in the future')
        return self


@router.put("/records/students/{student_id}/status")
def change_status(student_id: uuid.UUID, body: StatusInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin_only)):
    acc = Access(db, ctx)
    student, user = get_student(db, acc, student_id, lock=True)
    if student.status == body.status and student.left_on == body.left_on and student.status_note == body.note:
        return dict(id=student.id, status=student.status)
    previous = student.status
    student.status, student.left_on, student.status_note = body.status, body.left_on, body.note
    if body.status != 'ACTIVE':
        # Leave current classes; marks, attendance and reports stay.
        scoped(db, Enrollment, ctx).filter(Enrollment.student_id == student.id, Enrollment.active.is_(True)).update(
            {Enrollment.active: False}, synchronize_session=False)
    # Transferred and withdrawn students can no longer sign in. Graduates keep read access to their records.
    if body.status in {'TRANSFERRED', 'WITHDRAWN'} and user.status == UserStatus.ACTIVE:
        user.status = UserStatus.DEACTIVATED
        user.password_changed_at = datetime.now(timezone.utc)
        db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked.is_(False)).update({AuthSession.revoked: True}, synchronize_session=False)
    elif body.status in {'ACTIVE', 'GRADUATED'} and user.status == UserStatus.DEACTIVATED and previous in {'TRANSFERRED', 'WITHDRAWN'}:
        user.status = UserStatus.ACTIVE
    record_audit(db, ctx, 'student.status_changed', student.id, ctx.institution_id,
                 f'{previous} to {body.status}' + (f' on {body.left_on}' if body.left_on else ''))
    commit(db)
    return dict(id=student.id, status=student.status)


# --- Guardians -------------------------------------------------------------------

def normalise_phone(value):
    raw = re.sub(r'[\s\-().]', '', value or '')
    if re.fullmatch(r'0[17]\d{8}', raw):
        raw = '+254' + raw[1:]
    elif re.fullmatch(r'254[17]\d{8}', raw):
        raw = '+' + raw
    if not re.fullmatch(r'\+?\d{7,15}', raw):
        raise HTTPException(422, 'Enter a valid phone number, for example 0712 345 678')
    return raw


def guardian_view(g, link=None, children=None):
    out = dict(id=g.id, full_name=g.full_name, phone=g.phone, email=g.email, occupation=g.occupation)
    if link is not None:
        out.update(relationship=link.relationship, is_primary=link.is_primary)
    if children is not None:
        out['children'] = children
    return out


def guardian_list(db, ctx, student_id):
    rows = scoped(db, StudentGuardian, ctx).join(Guardian, Guardian.id == StudentGuardian.guardian_id).filter(
        Guardian.institution_id == ctx.institution_id, StudentGuardian.student_id == student_id
    ).with_entities(Guardian, StudentGuardian).order_by(StudentGuardian.is_primary.desc(), Guardian.full_name).all()
    return [guardian_view(g, link) for g, link in rows]


class GuardianDetails(Input):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=7, max_length=25)
    email: str | None = Field(default=None, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    occupation: str = Field(default='', max_length=120)


class GuardianLink(GuardianDetails):
    relationship: str = Field(min_length=2, max_length=40)
    is_primary: bool = False


@router.get("/records/students/{student_id}/guardians")
def student_guardians(student_id: uuid.UUID, db: Session = Depends(get_db), acc: Access = Depends(access)):
    acc.need('guardians')
    get_student(db, acc, student_id)
    return guardian_list(db, acc.ctx, student_id)


@router.post("/records/students/{student_id}/guardians", status_code=201)
def add_guardian(student_id: uuid.UUID, body: GuardianLink, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin_only)):
    acc = Access(db, ctx)
    student, _ = get_student(db, acc, student_id, lock=True)
    phone = normalise_phone(body.phone)
    guardian = scoped(db, Guardian, ctx).filter_by(phone=phone).with_for_update().first()
    matched = guardian is not None
    if guardian is None:
        guardian = Guardian(institution_id=ctx.institution_id, full_name=body.full_name, phone=phone,
                            email=str(body.email) if body.email else None, occupation=body.occupation)
        db.add(guardian)
        db.flush()
    if scoped(db, StudentGuardian, ctx).filter_by(student_id=student.id, guardian_id=guardian.id).first():
        raise HTTPException(409, 'This guardian is already linked to the student')
    if body.is_primary:
        scoped(db, StudentGuardian, ctx).filter_by(student_id=student.id).update({StudentGuardian.is_primary: False}, synchronize_session=False)
    first = not scoped(db, StudentGuardian, ctx).filter_by(student_id=student.id).first()
    db.add(StudentGuardian(institution_id=ctx.institution_id, student_id=student.id, guardian_id=guardian.id,
                           relationship=body.relationship, is_primary=body.is_primary or first))
    record_audit(db, ctx, 'guardian.linked', student.id, ctx.institution_id, 'Existing guardian matched by phone' if matched else 'New guardian')
    commit(db)
    return dict(guardians=guardian_list(db, ctx, student.id), matched_existing=matched,
                message=f'{guardian.full_name} was already on record with this phone number and is now linked.' if matched else 'Guardian added')


@router.put("/records/guardians/{guardian_id}")
def edit_guardian(guardian_id: uuid.UUID, body: GuardianDetails, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin_only)):
    guardian = scoped(db, Guardian, ctx).filter_by(id=guardian_id).with_for_update().first()
    if not guardian:
        missing()
    guardian.full_name, guardian.phone = body.full_name, normalise_phone(body.phone)
    guardian.email, guardian.occupation = (str(body.email) if body.email else None), body.occupation
    record_audit(db, ctx, 'guardian.updated', guardian.id, ctx.institution_id)
    commit(db)
    return guardian_view(guardian)


class LinkEdit(Input):
    relationship: str = Field(min_length=2, max_length=40)
    is_primary: bool = False


@router.put("/records/students/{student_id}/guardians/{guardian_id}")
def edit_link(student_id: uuid.UUID, guardian_id: uuid.UUID, body: LinkEdit, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin_only)):
    get_student(db, Access(db, ctx), student_id, lock=True)
    link = scoped(db, StudentGuardian, ctx).filter_by(student_id=student_id, guardian_id=guardian_id).first()
    if not link:
        missing()
    if body.is_primary:
        scoped(db, StudentGuardian, ctx).filter_by(student_id=student_id).update({StudentGuardian.is_primary: False}, synchronize_session=False)
    link.relationship, link.is_primary = body.relationship, body.is_primary
    commit(db)
    return guardian_list(db, ctx, student_id)


@router.delete("/records/students/{student_id}/guardians/{guardian_id}")
def unlink_guardian(student_id: uuid.UUID, guardian_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin_only)):
    get_student(db, Access(db, ctx), student_id, lock=True)
    link = scoped(db, StudentGuardian, ctx).filter_by(student_id=student_id, guardian_id=guardian_id).first()
    if not link:
        missing()
    db.delete(link)
    db.flush()
    # A guardian with no children left is removed; siblings keep theirs.
    if not scoped(db, StudentGuardian, ctx).filter_by(guardian_id=guardian_id).first():
        guardian = scoped(db, Guardian, ctx).filter_by(id=guardian_id).first()
        if guardian:
            db.delete(guardian)
    record_audit(db, ctx, 'guardian.unlinked', student_id, ctx.institution_id)
    commit(db)
    return guardian_list(db, ctx, student_id)


@router.get("/records/guardians")
def guardians(search: str = Query('', max_length=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), acc: Access = Depends(access)):
    acc.need('guardians')
    if acc.supervisor and not acc.admin and 'students.view' not in acc.perms:
        raise HTTPException(403, "You do not have permission to perform this action")
    ctx = acc.ctx
    q = scoped(db, Guardian, ctx)
    if search:
        term = like(search)
        q = q.filter(or_(Guardian.full_name.ilike(term, escape='\\'), Guardian.phone.ilike(term, escape='\\')))
    total = q.count()
    page = q.order_by(Guardian.full_name, Guardian.id).offset(offset).limit(PAGE).all()
    links = scoped(db, StudentGuardian, ctx).join(Student, Student.id == StudentGuardian.student_id).join(User, User.id == Student.user_id).filter(
        Student.institution_id == ctx.institution_id, StudentGuardian.guardian_id.in_([g.id for g in page] or [uuid.uuid4()])
    ).with_entities(StudentGuardian, Student, User).all()
    children = {}
    for link, s, u in links:
        children.setdefault(link.guardian_id, []).append(dict(id=s.id, name=f'{u.first_name} {u.last_name}', admission_number=s.admission_number,
                                                              relationship=link.relationship, status=s.status))
    return dict(total=total, items=[guardian_view(g, children=children.get(g.id, [])) for g in page])


# --- Fee status ------------------------------------------------------------------

def fee_view(fee, period):
    return dict(period_id=period.id, period_name=period.name, status=fee.status, balance=fee.balance, note=fee.note,
                updated_at=fee.updated_at)


def institution_periods(db, ctx):
    rows = scoped(db, AcademicPeriod, ctx).join(AcademicYear, AcademicYear.id == AcademicPeriod.year_id).filter(
        AcademicYear.institution_id == ctx.institution_id).with_entities(AcademicPeriod, AcademicYear).order_by(AcademicPeriod.start_date.desc()).all()
    return [dict(id=p.id, name=p.name, year=y.name, start_date=p.start_date, end_date=p.end_date) for p, y in rows]


def get_period(db, ctx, period_id):
    period = scoped(db, AcademicPeriod, ctx).filter_by(id=period_id).first()
    if not period:
        missing()
    return period


def fee_students(db, acc, class_id=None):
    q = student_query(db, acc)
    if acc.supervisor and not acc.admin and 'fees.manage' not in acc.perms:
        # Class teachers see only their own classes, even with students.view.
        mine = scoped(db, Enrollment, acc.ctx).filter(Enrollment.class_id.in_(acc.classes or [uuid.uuid4()]), Enrollment.active.is_(True)).with_entities(Enrollment.student_id)
        q = q.filter(Student.id.in_(mine))
    if class_id:
        q = q.filter(Student.id.in_(scoped(db, Enrollment, acc.ctx).filter(Enrollment.class_id == class_id, Enrollment.active.is_(True)).with_entities(Enrollment.student_id)))
    return q


@router.get("/records/fees")
def fees(period_id: uuid.UUID | None = None, class_id: uuid.UUID | None = None,
         status: Literal['PAID', 'PARTIAL', 'UNPAID', 'NONE', ''] = '', search: str = Query('', max_length=100),
         offset: int = Query(0, ge=0), db: Session = Depends(get_db), acc: Access = Depends(access)):
    acc.need('fees')
    ctx = acc.ctx
    periods = institution_periods(db, ctx)
    if period_id is None:
        today = date.today()
        period_id = next((p['id'] for p in periods if p['start_date'] <= today <= p['end_date']), periods[0]['id'] if periods else None)
    classes = visible_classes(db, acc) if acc.admin or 'fees.manage' in acc.perms else [c for c in visible_classes(db, acc) if c['id'] in set(acc.classes or [])]
    if period_id is None:
        return dict(periods=[], period_id=None, classes=classes, items=[], total=0, totals={}, can=acc.flags())
    get_period(db, ctx, period_id)
    q = fee_students(db, acc, class_id).filter(Student.status == 'ACTIVE').outerjoin(
        FeeStatus, (FeeStatus.student_id == Student.id) & (FeeStatus.institution_id == Student.institution_id) & (FeeStatus.period_id == period_id))
    if search:
        term = like(search)
        q = q.filter(or_(*(c.ilike(term, escape='\\') for c in [Student.admission_number, User.first_name, User.last_name])))
    totals = {key or 'NONE': dict(count=n, balance=bal or 0) for key, n, bal in q.with_entities(
        FeeStatus.status, func.count(Student.id), func.sum(FeeStatus.balance)).group_by(FeeStatus.status).all()}
    if status == 'NONE':
        q = q.filter(FeeStatus.id.is_(None))
    elif status:
        q = q.filter(FeeStatus.status == status)
    total = q.count()
    page = q.with_entities(Student, User, FeeStatus).order_by(User.first_name, User.last_name, Student.id).offset(offset).limit(PAGE).all()
    group = current_classes(db, ctx, [s.id for s, _, _ in page])
    items = [dict(student_row(s, u, group), fee=dict(status=f.status, balance=f.balance, note=f.note, updated_at=f.updated_at) if f else None)
             for s, u, f in page]
    return dict(periods=periods, period_id=period_id, classes=classes, items=items, total=total, totals=totals, can=acc.flags())


class FeeInput(Input):
    period_id: uuid.UUID
    status: Literal['PAID', 'PARTIAL', 'UNPAID']
    balance: Decimal = Field(default=Decimal('0'), ge=0, le=100000000, max_digits=12, decimal_places=2)
    note: str = Field(default='', max_length=300)

    @model_validator(mode='after')
    def consistent(self):
        if self.status == 'PAID':
            self.balance = Decimal('0')
        elif self.status == 'PARTIAL' and self.balance <= 0:
            raise ValueError('A partly paid student must have a balance above zero')
        return self


def save_fee(db, ctx, student_id, body):
    row = scoped(db, FeeStatus, ctx).filter_by(student_id=student_id, period_id=body.period_id).with_for_update().first()
    if row is None:
        row = FeeStatus(institution_id=ctx.institution_id, student_id=student_id, period_id=body.period_id)
        db.add(row)
    changed = (row.status, row.balance, row.note) != (body.status, body.balance, body.note)
    row.status, row.balance, row.note, row.updated_by = body.status, body.balance, body.note, ctx.actor_user_id or ctx.user_id
    return row, changed


@router.put("/records/fees/{student_id}")
def set_fee(student_id: uuid.UUID, body: FeeInput, db: Session = Depends(get_db), acc: Access = Depends(access)):
    acc.need('edit_fees')
    ctx = acc.ctx
    get_student(db, acc, student_id, lock=True)
    period = get_period(db, ctx, body.period_id)
    row, changed = save_fee(db, ctx, student_id, body)
    if changed:
        record_audit(db, ctx, 'fees.status_updated', student_id, ctx.institution_id, f'{period.name}: {body.status}, balance {body.balance}')
    commit(db)
    return fee_view(row, period)


class FeeImportRow(Input):
    admission_number: str = Field(min_length=1, max_length=60)
    status: str = Field(max_length=20)
    balance: str = Field(default='', max_length=30)
    note: str = Field(default='', max_length=300)


class FeeImport(Input):
    period_id: uuid.UUID
    rows: list[FeeImportRow] = Field(min_length=1, max_length=5000)
    commit: bool = False


STATUS_WORDS = {'PAID': 'PAID', 'CLEARED': 'PAID', 'PARTIAL': 'PARTIAL', 'PARTLY PAID': 'PARTIAL', 'PARTIALLY PAID': 'PARTIAL',
                'UNPAID': 'UNPAID', 'NOT PAID': 'UNPAID'}


@router.post("/records/fees/import")
def import_fees(body: FeeImport, db: Session = Depends(get_db), acc: Access = Depends(access)):
    """Check a list from the finance system, then apply it only when every row is valid."""
    acc.need('edit_fees')
    ctx = acc.ctx
    period = get_period(db, ctx, body.period_id)
    # Admission numbers match without regard to case or surrounding spaces.
    known = {number.strip().upper(): (sid, status) for sid, number, status in scoped(db, Student, ctx).with_entities(
        Student.id, Student.admission_number, Student.status).all()}
    seen, results, valid = set(), [], []
    for index, r in enumerate(body.rows, start=1):
        problems = []
        key = r.admission_number.strip().upper()
        student = known.get(key)
        if student is None:
            problems.append('No student with this admission number')
        elif student[1] != 'ACTIVE':
            problems.append(f'This student is marked {student[1].lower()}')
        if key in seen:
            problems.append('Admission number appears more than once')
        seen.add(key)
        status = STATUS_WORDS.get(r.status.strip().upper())
        if status is None:
            problems.append('Status must be Paid, Partial or Unpaid')
        balance = Decimal('0')
        text = r.balance.replace(',', '').replace('KES', '').replace('Ksh', '').strip()
        if text:
            try:
                balance = Decimal(text)
            except Exception:
                problems.append('Balance must be a number')
        if balance < 0:
            problems.append('Balance cannot be negative')
        try:
            fee = FeeInput(period_id=period.id, status=status or 'UNPAID', balance=balance, note=r.note) if not problems else None
        except ValueError as exc:
            problems.append(str(exc).split('\n')[-1].replace('Value error, ', '').strip())
            fee = None
        results.append(dict(row=index, admission_number=r.admission_number, status=status, balance=balance if not problems else None, problems=problems))
        if not problems:
            valid.append((student, fee))
    errors = sum(1 for r in results if r['problems'])
    if body.commit:
        if errors:
            raise HTTPException(422, 'Fix the rows with problems before applying the list')
        for student, fee in valid:
            save_fee(db, ctx, student[0], fee)
        record_audit(db, ctx, 'fees.list_imported', period.id, ctx.institution_id, f'{period.name}: {len(valid)} students')
        commit(db)
    return dict(period_name=period.name, rows=results, valid=len(valid), errors=errors, applied=bool(body.commit))


# --- Discipline ------------------------------------------------------------------

def discipline_view(r):
    return dict(id=r.id, student_id=r.student_id, occurred_on=r.occurred_on, category=r.category, description=r.description,
                action_taken=r.action_taken, recorded_by=r.recorded_by, created_at=r.created_at)


class DisciplineInput(Input):
    occurred_on: date
    category: str = Field(min_length=2, max_length=60)
    description: str = Field(min_length=3, max_length=5000)
    action_taken: str = Field(default='', max_length=5000)

    @model_validator(mode='after')
    def not_future(self):
        if self.occurred_on > date.today():
            raise ValueError('The date cannot be in the future')
        return self


@router.get("/records/students/{student_id}/discipline")
def discipline(student_id: uuid.UUID, db: Session = Depends(get_db), acc: Access = Depends(access)):
    acc.need('discipline')
    get_student(db, acc, student_id)
    return [discipline_view(r) for r in scoped(db, DisciplineRecord, acc.ctx).filter_by(student_id=student_id).order_by(
        DisciplineRecord.occurred_on.desc(), DisciplineRecord.created_at.desc()).all()]


@router.post("/records/students/{student_id}/discipline", status_code=201)
def add_discipline(student_id: uuid.UUID, body: DisciplineInput, db: Session = Depends(get_db), acc: Access = Depends(access)):
    acc.need('discipline')
    ctx = acc.ctx
    get_student(db, acc, student_id)
    row = DisciplineRecord(institution_id=ctx.institution_id, student_id=student_id, recorded_by=ctx.actor_user_id or ctx.user_id, **body.model_dump())
    db.add(row)
    record_audit(db, ctx, 'discipline.recorded', student_id, ctx.institution_id, body.category)
    commit(db)
    return discipline_view(row)


def own_discipline(db, acc, record_id):
    row = scoped(db, DisciplineRecord, acc.ctx).filter_by(id=record_id).with_for_update().first()
    if not row:
        missing()
    get_student(db, acc, row.student_id)
    # Class teachers may change only what they recorded.
    if not acc.admin and row.recorded_by != acc.ctx.user_id:
        raise HTTPException(403, 'Only the person who recorded this, or an institution administrator, can change it')
    return row


@router.put("/records/discipline/{discipline_id}")
def edit_discipline(discipline_id: uuid.UUID, body: DisciplineInput, db: Session = Depends(get_db), acc: Access = Depends(access)):
    acc.need('discipline')
    row = own_discipline(db, acc, discipline_id)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    record_audit(db, acc.ctx, 'discipline.updated', row.student_id, acc.ctx.institution_id, body.category)
    commit(db)
    return discipline_view(row)


@router.delete("/records/discipline/{discipline_id}")
def delete_discipline(discipline_id: uuid.UUID, db: Session = Depends(get_db), acc: Access = Depends(access)):
    acc.need('discipline')
    row = own_discipline(db, acc, discipline_id)
    record_audit(db, acc.ctx, 'discipline.deleted', row.student_id, acc.ctx.institution_id, row.category)
    db.delete(row)
    commit(db)
    return {'message': 'Record deleted'}


# --- Announcements -----------------------------------------------------------------

class AnnouncementInput(Input):
    title: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=3, max_length=10000)
    audience: Literal['EVERYONE', 'STAFF', 'STUDENTS', 'CLASS']
    class_id: uuid.UUID | None = None
    expires_on: date | None = None

    @model_validator(mode='after')
    def class_audience(self):
        if (self.audience == 'CLASS') != (self.class_id is not None):
            raise ValueError('Choose a class only when the audience is a class')
        return self


def announcement_view(row, classes, authors):
    return dict(id=row.id, title=row.title, body=row.body, audience=row.audience, class_id=row.class_id,
                class_name=classes.get(row.class_id), expires_on=row.expires_on, created_at=row.created_at,
                author=authors.get(row.created_by))


@router.get("/announcements")
def announcements(include_expired: bool = False, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    q = scoped(db, Announcement, ctx)
    today = date.today()
    if ctx.role != UserRole.INSTITUTION_ADMIN or not include_expired:
        q = q.filter(or_(Announcement.expires_on.is_(None), Announcement.expires_on >= today))
    if ctx.role == UserRole.STUDENT:
        student = scoped(db, Student, ctx).filter_by(user_id=ctx.user_id).first()
        mine = scoped(db, Enrollment, ctx).filter(Enrollment.student_id == (student.id if student else None), Enrollment.active.is_(True)).with_entities(Enrollment.class_id)
        q = q.filter(or_(Announcement.audience.in_(['EVERYONE', 'STUDENTS']), (Announcement.audience == 'CLASS') & Announcement.class_id.in_(mine)))
    elif ctx.role == UserRole.TEACHER:
        supervised = scoped(db, AcademicClass, ctx).filter(AcademicClass.supervisor_id == ctx.user_id).with_entities(AcademicClass.id)
        taught = scoped(db, Subject, ctx).filter(Subject.id.in_(taught_subject_ids(db, ctx))).with_entities(Subject.class_id)
        q = q.filter(or_(Announcement.audience.in_(['EVERYONE', 'STAFF']),
                         (Announcement.audience == 'CLASS') & or_(Announcement.class_id.in_(supervised), Announcement.class_id.in_(taught))))
    elif ctx.role != UserRole.INSTITUTION_ADMIN:
        q = q.filter(Announcement.audience.in_(['EVERYONE', 'STAFF']))
    rows = q.order_by(Announcement.created_at.desc()).limit(100).all()
    classes = {c.id: f"{c.name}{' ' + c.stream if c.stream else ''}" for c in scoped(db, AcademicClass, ctx).filter(
        AcademicClass.id.in_([r.class_id for r in rows if r.class_id] or [uuid.uuid4()])).all()}
    authors = {u.id: f'{u.first_name} {u.last_name}' for u in db.query(User).filter(
        User.institution_id == ctx.institution_id, User.id.in_({r.created_by for r in rows} or {uuid.uuid4()})).all()}
    return [announcement_view(r, classes, authors) for r in rows]


def check_class(db, ctx, class_id):
    if class_id and not scoped(db, AcademicClass, ctx).filter_by(id=class_id).first():
        missing()


@router.post("/announcements", status_code=201)
def post_announcement(body: AnnouncementInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin_only)):
    check_class(db, ctx, body.class_id)
    row = Announcement(institution_id=ctx.institution_id, created_by=ctx.actor_user_id or ctx.user_id, **body.model_dump())
    db.add(row)
    record_audit(db, ctx, 'announcement.posted', None, ctx.institution_id, body.title[:80])
    commit(db)
    return dict(id=row.id)


@router.put("/announcements/{announcement_id}")
def edit_announcement(announcement_id: uuid.UUID, body: AnnouncementInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin_only)):
    row = scoped(db, Announcement, ctx).filter_by(id=announcement_id).first()
    if not row:
        missing()
    check_class(db, ctx, body.class_id)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    commit(db)
    return dict(id=row.id)


@router.delete("/announcements/{announcement_id}")
def delete_announcement(announcement_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin_only)):
    row = scoped(db, Announcement, ctx).filter_by(id=announcement_id).first()
    if not row:
        missing()
    record_audit(db, ctx, 'announcement.deleted', row.id, ctx.institution_id, row.title[:80])
    db.delete(row)
    commit(db)
    return {'message': 'Announcement removed'}


# --- Attendance percentages --------------------------------------------------------

@router.get("/attendance/summary")
def attendance_summary(class_id: uuid.UUID, period_id: uuid.UUID | None = None, db: Session = Depends(get_db),
                       ctx: AuthContext = Depends(require_role(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN))):
    """Per student: the class register and each subject as a percentage for a term or semester."""
    group = get_class(db, class_id, ctx)
    supervises = ctx.role == UserRole.INSTITUTION_ADMIN or group.supervisor_id == ctx.user_id
    window = attendance_service.date_range(db, ctx.institution_id, group, period_id)
    if window is None:
        missing()
    subjects = scoped(db, Subject, ctx).filter(Subject.class_id == class_id)
    if not supervises:
        subjects = subjects.filter(Subject.id.in_(taught_subject_ids(db, ctx)))
    subjects = subjects.order_by(Subject.name).all()
    columns = ([dict(key='class', label='Class register')] if supervises else []) + [dict(key=str(s.id), label=s.name) for s in subjects]
    keys = [c['key'] for c in columns]
    roster = scoped(db, Student, ctx).join(Enrollment, Enrollment.student_id == Student.id).join(User, User.id == Student.user_id).filter(
        Enrollment.institution_id == ctx.institution_id, Enrollment.class_id == class_id, Enrollment.active.is_(True),
        User.institution_id == ctx.institution_id).with_entities(Student, User).order_by(User.first_name, User.last_name).all()
    counts = attendance_service.counts(db, ctx.institution_id, [class_id], window['start'], window['end'],
                                       [s.id for s, _ in roster], keys) if roster and keys else {}
    rows = []
    for student, user in roster:
        cells = {key: attendance_service.percent(counts.get((student.id, key), {})) for key in keys}
        subject_total = attendance_service.merge(*(counts.get((student.id, key), {}) for key in keys if key != 'class'))
        rows.append(dict(student_id=student.id, name=f'{user.first_name} {user.last_name}', admission_number=student.admission_number,
                         cells=cells, subjects=attendance_service.percent(subject_total)))
    return dict(class_id=class_id, label=window['label'], period_id=window['period_id'], periods=window['periods'],
                start=window['start'] if window['start'] != date.min else None, end=window['end'] if window['end'] != date.max else None,
                columns=columns, rows=rows)


@router.get("/student/attendance/summary")
def my_attendance_summary(period_id: uuid.UUID | None = None, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_role(UserRole.STUDENT))):
    from app.api.routes.learning import own_student, student_subjects
    student = own_student(db, ctx)
    classes = scoped(db, AcademicClass, ctx).filter(AcademicClass.id.in_(scoped(db, Enrollment, ctx).filter(
        Enrollment.student_id == student.id, Enrollment.active.is_(True)).with_entities(Enrollment.class_id))).all()
    if not classes:
        return dict(label=None, periods=[], period_id=None, rows=[], overall=attendance_service.percent({}))
    group = classes[0]
    window = attendance_service.date_range(db, ctx.institution_id, group, period_id)
    if window is None:
        missing()
    subjects = student_subjects(db, student, ctx).order_by(Subject.name).all()
    keys = ['class'] + [str(s.id) for s in subjects]
    counts = attendance_service.counts(db, ctx.institution_id, [c.id for c in classes], window['start'], window['end'], [student.id], keys)
    rows = [dict(key='class', label='Class register', **attendance_service.percent(counts.get((student.id, 'class'), {})))]
    rows += [dict(key=str(s.id), label=s.name, **attendance_service.percent(counts.get((student.id, str(s.id)), {}))) for s in subjects]
    overall = attendance_service.merge(*(counts.get((student.id, str(s.id)), {}) for s in subjects))
    return dict(label=window['label'], periods=window['periods'], period_id=window['period_id'], rows=rows,
                overall=attendance_service.percent(overall))
