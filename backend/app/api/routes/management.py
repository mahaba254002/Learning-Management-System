"""Institution modules, employee directory, staff accounts, teaching allocations and staff registers."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import AuthContext, require_platform_admin, require_role, require_tenant_user
from app.core.permissions import granted_permissions, require_permission
from app.db.session import get_db
from app.models.institution import Institution, InstitutionStatus
from app.models.user import User, UserRole, UserStatus
from app.models.academic import AcademicClass, Enrollment, Student, Subject
from app.models.curriculum import Department
from app.models.management import StaffMember, StaffAttendance
from app.models.pilot import AcademicYear
from app.models.structure import STAFF_PERMISSIONS, OfferingTeacher, StaffPermission
from app.schemas.academic import Input
from app.services.modules import InstitutionModules, DEPENDENCIES, institution_modules, module_presets, require_enabled
from app.services.audit_service import record_audit
from app.services.subscriptions import kenya_today
from app.services import staff as staff_service
from app.core import tenancy
from app.api.routes.teaching import admin, staff, scoped, commit, sync_lead, taught_subject_ids

router = APIRouter(prefix='/api', tags=['Institution management'])


def view(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def owned(db, model, identity, tenant, lock=False):
    if identity is None: raise HTTPException(404, 'Management record not found')
    return tenancy.owned(db, model, identity, tenant, lock=lock, not_found='Management record not found')


def unchanged(row, expected):
    try:
        supplied = datetime.fromisoformat(expected.replace('Z', '+00:00'))
        current = row.updated_at
        supplied = supplied.replace(tzinfo=timezone.utc) if supplied.tzinfo is None else supplied
        current = current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(409, 'Reload this record before saving your changes.')
    if supplied != current:
        raise HTTPException(409, 'This record changed. Reload before saving your changes.')


def module_view(row):
    return dict(modules=institution_modules(row), presets=module_presets(), dependencies=DEPENDENCIES,
                updated_at=row.updated_at, configured=bool(row.module_settings))


@router.get('/institution/modules')
def modules(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    return module_view(db.get(Institution, ctx.institution_id))


@router.get('/platform/module-presets')
def presets(ctx: AuthContext = Depends(require_platform_admin)):
    return dict(presets=module_presets(), dependencies=DEPENDENCIES)


@router.get('/platform/institutions/{institution_id}/modules')
def platform_modules(institution_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    row = db.get(Institution, institution_id)
    if not row: raise HTTPException(404, 'Institution not found')
    return module_view(row)


class ModulesInput(Input):
    modules: InstitutionModules
    expected_updated_at: str = Field(max_length=60)


@router.put('/platform/institutions/{institution_id}/modules')
def save_modules(institution_id: uuid.UUID, body: ModulesInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    row = db.query(Institution).filter_by(id=institution_id).with_for_update().first()
    if not row: raise HTTPException(404, 'Institution not found')
    if row.status == InstitutionStatus.ARCHIVED: raise HTTPException(409, 'Archived institutions cannot be configured')
    unchanged(row, body.expected_updated_at)
    previous = institution_modules(row)
    row.module_settings = body.modules.model_dump()
    changes = ', '.join(f'{key}={value}' for key, value in row.module_settings.items() if previous[key] != value)
    record_audit(db, ctx, 'institution.modules_updated', row.id, row.id, changes[:500])
    commit(db)
    return module_view(row)


# --- Departments and faculties ---------------------------------------------

class DepartmentInput(Input):
    code: str = Field(min_length=1, max_length=30, pattern=r'^[A-Za-z0-9._/-]+$')
    name: str = Field(min_length=1, max_length=160)
    kind: Literal['FACULTY', 'SCHOOL', 'DEPARTMENT'] = 'DEPARTMENT'
    parent_id: uuid.UUID | None = None
    expected_updated_at: str | None = Field(default=None, max_length=60)


def check_department(db, ctx, body, row=None):
    """Faculties and schools sit at the top; only departments sit under them."""
    if body.parent_id is not None:
        if body.kind != 'DEPARTMENT': raise HTTPException(422, 'Only a department can sit under a faculty or school')
        parent = owned(db, Department, body.parent_id, ctx.institution_id)
        if parent.kind == 'DEPARTMENT': raise HTTPException(422, 'Choose a faculty or school as the parent')
    if row is not None and body.kind == 'DEPARTMENT' and row.kind != 'DEPARTMENT' and scoped(db, Department, ctx).filter_by(parent_id=row.id).first():
        raise HTTPException(409, 'Move the departments under this faculty first')


@router.get('/management/departments')
def departments(db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    return [view(row) for row in scoped(db, Department, ctx).order_by(Department.name)]


@router.post('/management/departments', status_code=201)
def create_department(body: DepartmentInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    check_department(db, ctx, body)
    row = Department(id=uuid.uuid4(), institution_id=ctx.institution_id, code=body.code.upper(), name=body.name,
                     kind=body.kind, parent_id=body.parent_id)
    db.add(row)
    record_audit(db, ctx, 'department.created', row.id, ctx.institution_id, body.kind)
    commit(db)
    return view(row)


@router.put('/management/departments/{department_id}')
def edit_department(department_id: uuid.UUID, body: DepartmentInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = owned(db, Department, department_id, ctx.institution_id, lock=True)
    unchanged(row, body.expected_updated_at)
    check_department(db, ctx, body, row)
    row.code, row.name, row.kind, row.parent_id = body.code.upper(), body.name, body.kind, body.parent_id
    record_audit(db, ctx, 'department.updated', row.id, ctx.institution_id, body.kind)
    commit(db)
    return view(row)


# --- Staff directory --------------------------------------------------------

class StaffInput(Input):
    staff_number: str = Field(min_length=1, max_length=40, pattern=r'^[A-Za-z0-9._/-]+$')
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    category: Literal['TEACHING', 'NON_TEACHING']
    job_title: str = Field(min_length=1, max_length=120)
    department_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    email: str | None = Field(default=None, max_length=255, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    phone: str | None = Field(default=None, max_length=50)
    employment_type: Literal['FULL_TIME', 'PART_TIME', 'CONTRACT', 'VOLUNTEER'] = 'FULL_TIME'
    status: Literal['ACTIVE', 'ON_LEAVE', 'INACTIVE'] = 'ACTIVE'
    joined_on: date | None = None
    gender: Literal['MALE', 'FEMALE', 'OTHER', 'PREFER_NOT_TO_SAY'] | None = None
    date_of_birth: date | None = None
    qualification: str | None = Field(default=None, max_length=255)
    specialization: str | None = Field(default=None, max_length=255)
    expected_updated_at: str | None = Field(default=None, max_length=60)


class NewStaffInput(StaffInput):
    # NONE keeps an HR record only. LINK emails a single-use set-password link.
    login: Literal['NONE', 'LINK', 'TEMPORARY_PASSWORD'] = 'NONE'

    @model_validator(mode='after')
    def login_needs_email(self):
        if self.login != 'NONE' and (not self.email or self.user_id): raise ValueError('A new sign-in account needs an email address')
        return self


STAFF_FIELDS = set(StaffInput.model_fields) - {'expected_updated_at'}


def closed_years(db, ctx):
    return scoped(db, AcademicYear, ctx).filter_by(status='CLOSED').with_entities(AcademicYear.name)


def open_teaching(db, ctx, user_id):
    """Offerings in open years that this person leads or co-teaches."""
    return scoped(db, Subject, ctx).join(AcademicClass, AcademicClass.id == Subject.class_id).filter(
        AcademicClass.institution_id == ctx.institution_id, Subject.id.in_(taught_subject_ids(db, ctx, user_id)),
        AcademicClass.academic_year.not_in(closed_years(db, ctx))).first()


def validate_staff(db, ctx, body, row=None):
    if body.department_id: owned(db, Department, body.department_id, ctx.institution_id)
    if body.user_id:
        account = owned(db, User, body.user_id, ctx.institution_id)
        linking_new_account = row is None or row.user_id != body.user_id
        if account.role != staff_service.role_for(body.category) or linking_new_account and account.status != UserStatus.ACTIVE:
            raise HTTPException(422, 'Link teaching staff to an active teacher account, and other staff to an active staff account')
    elif row is not None and row.user_id:
        raise HTTPException(409, 'Close the sign-in account from its status controls instead of unlinking it')
    if row and row.user_id and (body.status != 'ACTIVE' or body.category != row.category) and open_teaching(db, ctx, row.user_id):
        raise HTTPException(409, 'Reassign this employee’s teaching allocations before changing their category or placing them on leave')


def account_view(user):
    if user is None: return None
    return dict(id=user.id, username=user.username, role=user.role, status=user.status,
                setup_pending=user.must_change_password)


def staff_view(row, user=None):
    return dict(view(row), account=account_view(user), teacher_user_id=row.user_id if row.category == 'TEACHING' else None)


@router.get('/management/options')
def options(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_permission('staff.view', 'staff_attendance.manage'))):
    enabled = institution_modules(db.get(Institution, ctx.institution_id))
    offerings = []
    if enabled['course_allocation'] and ctx.role == UserRole.INSTITUTION_ADMIN:
        rows = scoped(db, Subject, ctx).join(AcademicClass, AcademicClass.id == Subject.class_id).filter(
            AcademicClass.institution_id == ctx.institution_id, AcademicClass.academic_year.not_in(closed_years(db, ctx))
        ).with_entities(Subject, AcademicClass).order_by(AcademicClass.academic_year.desc(), AcademicClass.name, Subject.name).all()
        offerings = [dict(id=s.id, name=s.name, class_name=c.name, stream=c.stream, academic_year=c.academic_year, teacher_id=s.teacher_id) for s, c in rows]
    return dict(departments=[view(row) for row in scoped(db, Department, ctx).order_by(Department.name)],
        offerings=offerings, permissions=STAFF_PERMISSIONS,
        teachers=[dict(id=row.id, name=f'{row.first_name} {row.last_name}', email=row.email, status=row.status)
                  for row in scoped(db, User, ctx).filter_by(role=UserRole.TEACHER).order_by(User.first_name)],
        accounts=[dict(id=row.id, name=f'{row.first_name} {row.last_name}', email=row.email, status=row.status, role=row.role)
                  for row in scoped(db, User, ctx).filter(User.role.in_([UserRole.TEACHER, UserRole.STAFF])).order_by(User.first_name)],
        staff=[dict(id=row.id, name=f'{row.first_name} {row.last_name}', staff_number=row.staff_number, category=row.category,
                    status=row.status, user_id=row.user_id)
               for row in scoped(db, StaffMember, ctx).order_by(StaffMember.first_name)])


@router.get('/management/staff')
def staff_list(search: str = Query('', max_length=100), category: Literal['TEACHING', 'NON_TEACHING'] | None = None,
               status: Literal['ACTIVE', 'ON_LEAVE', 'INACTIVE'] | None = None, department_id: uuid.UUID | None = None,
               include_archived: bool = False, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
               db: Session = Depends(get_db), ctx: AuthContext = Depends(require_permission('staff.view'))):
    query = scoped(db, StaffMember, ctx).outerjoin(User, User.id == StaffMember.user_id)
    if not include_archived:
        query = query.filter(or_(User.id.is_(None), User.status != UserStatus.ARCHIVED))
    if search:
        term = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(or_(*(column.ilike(term, escape='\\') for column in [StaffMember.staff_number, StaffMember.first_name, StaffMember.last_name, StaffMember.job_title])))
    if category: query = query.filter(StaffMember.category == category)
    if status: query = query.filter(StaffMember.status == status)
    if department_id: query = query.filter(StaffMember.department_id == department_id)
    page = query.with_entities(StaffMember, User).order_by(StaffMember.first_name, StaffMember.last_name, StaffMember.id).offset(offset).limit(limit).all()
    return dict(total=query.count(), items=[staff_view(row, user) for row, user in page])


def write_account(db, ctx, profile, delivery):
    """Create a login for this record and deliver it. Commits."""
    institution = db.get(Institution, ctx.institution_id)
    try:
        user, link, temporary = staff_service.create_account(db, profile, institution, ctx.actor_user_id or ctx.user_id, delivery)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Could not create this account. The email address may already be in use.')
    record_audit(db, ctx, 'staff.account_created', profile.id, ctx.institution_id, f'{user.role.value}; {delivery}')
    commit(db)
    return deliver(db, user, institution, link, temporary)


def deliver(db, user, institution, link, temporary):
    emailed = staff_service.send_setup_link(db, user, institution, link) if link else False
    # The link is shown only when email failed, so the admin can pass it on in person.
    return dict(user_id=user.id, username=user.username, role=user.role, emailed=emailed,
                setup_link=link if link and not emailed else None, temporary_password=temporary,
                link_expires_in_hours=staff_service.SETUP_LINK_HOURS if link else None)


@router.post('/management/staff', status_code=201)
def create_staff(body: NewStaffInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    if body.login != 'NONE' and ctx.actor_user_id is not None:
        raise HTTPException(403, 'Return to your own workspace to create or change sign-in details.')
    validate_staff(db, ctx, body)
    row = StaffMember(id=uuid.uuid4(), institution_id=ctx.institution_id, **body.model_dump(include=STAFF_FIELDS))
    row.staff_number = row.staff_number.upper()
    db.add(row)
    record_audit(db, ctx, 'staff.created', row.id, ctx.institution_id)
    if body.login == 'NONE':
        commit(db)
        return staff_view(row, db.get(User, row.user_id) if row.user_id else None)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Could not save these details. Check for duplicate or conflicting records.')
    credentials = write_account(db, ctx, row, body.login)
    return dict(staff_view(row, db.get(User, row.user_id)), credentials=credentials)


@router.put('/management/staff/{staff_id}')
def edit_staff(staff_id: uuid.UUID, body: StaffInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = owned(db, StaffMember, staff_id, ctx.institution_id, lock=True)
    unchanged(row, body.expected_updated_at)
    validate_staff(db, ctx, body, row)
    for key, value in body.model_dump(include=STAFF_FIELDS).items(): setattr(row, key, value)
    row.staff_number = row.staff_number.upper()
    user = db.get(User, row.user_id) if row.user_id else None
    if user is not None:
        user.first_name, user.last_name = row.first_name, row.last_name
    record_audit(db, ctx, 'staff.updated', row.id, ctx.institution_id)
    commit(db)
    return staff_view(row, user)


class AccountInput(Input):
    delivery: Literal['LINK', 'TEMPORARY_PASSWORD'] = 'LINK'


@router.post('/management/staff/{staff_id}/account')
def staff_account(staff_id: uuid.UUID, body: AccountInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    """Create a sign-in for an employee, or send a fresh setup link if they have not used theirs."""
    if ctx.actor_user_id is not None: raise HTTPException(403, 'Return to your own workspace to create or change sign-in details.')
    row = owned(db, StaffMember, staff_id, ctx.institution_id, lock=True)
    if row.user_id is None:
        return write_account(db, ctx, row, body.delivery)
    user = db.query(User).filter_by(id=row.user_id, institution_id=ctx.institution_id).with_for_update().one()
    if not user.must_change_password: raise HTTPException(409, 'This person has already set their password. They can reset it from the sign-in page.')
    if user.status != UserStatus.ACTIVE: raise HTTPException(409, 'Reactivate this account first')
    institution = db.get(Institution, ctx.institution_id)
    link = temporary = None
    if body.delivery == 'LINK':
        link = staff_service.issue_setup_link(db, user, ctx.user_id)
    else:
        from datetime import timedelta
        from app.core.security import hash_password
        from app.services.password_service import generate_temporary_password
        temporary = generate_temporary_password()
        user.password_hash = hash_password(temporary)
        user.temporary_password_expires_at = datetime.now(timezone.utc) + timedelta(days=staff_service.TEMPORARY_PASSWORD_DAYS)
        user.password_changed_at = datetime.now(timezone.utc)
    record_audit(db, ctx, 'staff.account_setup_reissued', row.id, ctx.institution_id, body.delivery)
    commit(db)
    return deliver(db, user, institution, link, temporary)


class PermissionsInput(Input):
    permissions: list[Literal[tuple(STAFF_PERMISSIONS)]] = Field(max_length=len(STAFF_PERMISSIONS))


def linked_staff_account(db, ctx, staff_id, lock=False):
    row = owned(db, StaffMember, staff_id, ctx.institution_id, lock=lock)
    user = db.get(User, row.user_id) if row.user_id else None
    if user is None or user.role != UserRole.STAFF: raise HTTPException(409, 'Permissions apply to non-teaching staff with a sign-in account')
    return row, user


@router.get('/management/staff/{staff_id}/permissions')
def staff_permissions(staff_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    _, user = linked_staff_account(db, ctx, staff_id)
    granted = sorted(p for (p,) in scoped(db, StaffPermission, ctx).filter_by(user_id=user.id).with_entities(StaffPermission.permission).all())
    return dict(available=STAFF_PERMISSIONS, granted=granted)


@router.put('/management/staff/{staff_id}/permissions')
def save_staff_permissions(staff_id: uuid.UUID, body: PermissionsInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    _, user = linked_staff_account(db, ctx, staff_id, lock=True)
    wanted = set(body.permissions)
    current = {p.permission: p for p in scoped(db, StaffPermission, ctx).filter_by(user_id=user.id).all()}
    for permission, row in current.items():
        if permission not in wanted: db.delete(row)
    for permission in wanted - set(current):
        db.add(StaffPermission(institution_id=ctx.institution_id, user_id=user.id, permission=permission, granted_by=ctx.actor_user_id or ctx.user_id))
    record_audit(db, ctx, 'staff.permissions_updated', user.id, ctx.institution_id, ', '.join(sorted(wanted)) or 'none')
    commit(db)
    return dict(available=STAFF_PERMISSIONS, granted=sorted(wanted))


@router.get('/staff/me')
def staff_me(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_role(UserRole.STAFF))):
    profile = scoped(db, StaffMember, ctx).filter_by(user_id=ctx.user_id).first()
    user = db.get(User, ctx.user_id)
    return dict(first_name=user.first_name, last_name=user.last_name, email=user.email, username=user.username,
                staff_number=profile.staff_number if profile else None, job_title=profile.job_title if profile else None,
                status=profile.status if profile else None,
                permissions=sorted(granted_permissions(db, ctx.institution_id, ctx.user_id)), labels=STAFF_PERMISSIONS)


@router.get('/management/students')
def student_directory(search: str = Query('', max_length=100), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                      db: Session = Depends(get_db), ctx: AuthContext = Depends(require_permission('students.view'))):
    """Read-only student list for staff with the students.view right."""
    query = scoped(db, Student, ctx).join(User, User.id == Student.user_id).filter(
        User.institution_id == ctx.institution_id, User.status != UserStatus.ARCHIVED)
    if search:
        term = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(or_(*(c.ilike(term, escape='\\') for c in [Student.admission_number, User.first_name, User.last_name])))
    total = query.count()
    page = query.with_entities(Student, User).order_by(User.first_name, User.last_name, Student.id).offset(offset).limit(limit).all()
    classes = dict(scoped(db, Enrollment, ctx).join(AcademicClass, AcademicClass.id == Enrollment.class_id).filter(
        Enrollment.active.is_(True), Enrollment.student_id.in_([s.id for s, _ in page])).with_entities(Enrollment.student_id, AcademicClass.name).all()) if page else {}
    return dict(total=total, items=[dict(id=s.id, admission_number=s.admission_number, first_name=u.first_name, last_name=u.last_name,
                                         status=u.status, class_name=classes.get(s.id)) for s, u in page])


# --- Teaching allocations (offering teachers) --------------------------------

class AllocationInput(Input):
    subject_id: uuid.UUID
    staff_id: uuid.UUID
    role: Literal['LEAD', 'ASSISTANT'] = 'ASSISTANT'
    group_name: str = Field(default='', max_length=100)
    weekly_hours: Decimal | None = Field(default=None, gt=0, le=168, max_digits=5, decimal_places=2)


class AllocationEdit(Input):
    role: Literal['LEAD', 'ASSISTANT']
    group_name: str = Field(default='', max_length=100)
    weekly_hours: Decimal | None = Field(default=None, gt=0, le=168, max_digits=5, decimal_places=2)
    expected_updated_at: str = Field(max_length=60)


def allocation_rows(db, ctx):
    return scoped(db, OfferingTeacher, ctx).join(Subject, Subject.id == OfferingTeacher.subject_id).join(
        AcademicClass, AcademicClass.id == Subject.class_id).outerjoin(
        StaffMember, (StaffMember.user_id == OfferingTeacher.user_id) & (StaffMember.institution_id == OfferingTeacher.institution_id)).join(
        User, User.id == OfferingTeacher.user_id).filter(Subject.institution_id == ctx.institution_id, AcademicClass.institution_id == ctx.institution_id)


def allocation_view(row, subject, group, profile, user):
    return dict(id=row.id, subject_id=subject.id, subject_name=subject.name, class_name=group.name, stream=group.stream,
                academic_year=group.academic_year, user_id=row.user_id, staff_id=profile.id if profile else None,
                staff_name=f'{user.first_name} {user.last_name}', staff_number=profile.staff_number if profile else None,
                role=row.role, group_name=row.group_name, weekly_hours=row.weekly_hours, updated_at=row.updated_at)


ALLOCATION_ENTITIES = (OfferingTeacher, Subject, AcademicClass, StaffMember, User)


@router.get('/management/allocations')
def allocations(staff_id: uuid.UUID | None = None, subject_id: uuid.UUID | None = None,
                offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    query = allocation_rows(db, ctx)
    if staff_id: query = query.filter(StaffMember.id == staff_id)
    if subject_id: query = query.filter(OfferingTeacher.subject_id == subject_id)
    total = query.count()
    rows = query.with_entities(*ALLOCATION_ENTITIES).order_by(AcademicClass.academic_year.desc(), AcademicClass.name, Subject.name,
                                                              OfferingTeacher.role, OfferingTeacher.id).offset(offset).limit(limit).all()
    return dict(total=total, items=[allocation_view(*row) for row in rows])


def check_workload(db, ctx, user_id, group, hours, exclude=None):
    if not hours: return
    query = allocation_rows(db, ctx).filter(OfferingTeacher.user_id == user_id, AcademicClass.academic_year == group.academic_year)
    if exclude is not None: query = query.filter(OfferingTeacher.id != exclude)
    total = query.with_entities(func.coalesce(func.sum(OfferingTeacher.weekly_hours), 0)).scalar()
    if Decimal(str(total)) + hours > 168: raise HTTPException(422, 'Combined weekly hours in this academic year cannot exceed 168')


def writable_offering(db, ctx, subject_id):
    from app.services.academic_calendar import writable_year
    subject = owned(db, Subject, subject_id, ctx.institution_id, lock=True)
    group = scoped(db, AcademicClass, ctx).filter_by(id=subject.class_id).one()
    writable_year(db, ctx.institution_id, group.academic_year)
    return subject, group


def make_lead(db, ctx, subject, user_id):
    # Record the current lead first, so they stay on as a co-teacher.
    sync_lead(db, ctx, subject)
    subject.teacher_id = user_id
    sync_lead(db, ctx, subject)


@router.post('/management/allocations', status_code=201)
def create_allocation(body: AllocationInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    subject, group = writable_offering(db, ctx, body.subject_id)
    employee = owned(db, StaffMember, body.staff_id, ctx.institution_id, lock=True)
    user = db.get(User, employee.user_id) if employee.user_id else None
    if employee.category != 'TEACHING' or employee.status != 'ACTIVE' or user is None or user.role != UserRole.TEACHER or user.status != UserStatus.ACTIVE:
        raise HTTPException(422, 'Allocations need an active teaching employee with an active teacher account')
    check_workload(db, ctx, user.id, group, body.weekly_hours)
    if scoped(db, OfferingTeacher, ctx).filter_by(subject_id=subject.id, user_id=user.id, group_name=body.group_name).first():
        raise HTTPException(409, 'This teacher already has this offering and group')
    row = OfferingTeacher(institution_id=ctx.institution_id, subject_id=subject.id, user_id=user.id, role='ASSISTANT',
                          group_name=body.group_name, weekly_hours=body.weekly_hours)
    db.add(row)
    db.flush()
    if body.role == 'LEAD':
        if body.group_name: raise HTTPException(422, 'The lead teacher covers the whole offering; leave the group empty')
        make_lead(db, ctx, subject, user.id)
    record_audit(db, ctx, 'staff.allocation_created', row.id, ctx.institution_id, f'{subject.id}; {body.role}')
    commit(db)
    return allocation_view(row, subject, group, employee, user)


def owned_allocation(db, ctx, allocation_id):
    row = owned(db, OfferingTeacher, allocation_id, ctx.institution_id, lock=True)
    subject, group = writable_offering(db, ctx, row.subject_id)
    return row, subject, group


@router.put('/management/allocations/{allocation_id}')
def edit_allocation(allocation_id: uuid.UUID, body: AllocationEdit, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row, subject, group = owned_allocation(db, ctx, allocation_id)
    unchanged(row, body.expected_updated_at)
    if row.role == 'LEAD' and body.role != 'LEAD': raise HTTPException(409, 'Make another teacher the lead first')
    if body.role == 'LEAD' and body.group_name: raise HTTPException(422, 'The lead teacher covers the whole offering; leave the group empty')
    check_workload(db, ctx, row.user_id, group, body.weekly_hours, exclude=row.id)
    row.group_name, row.weekly_hours = body.group_name, body.weekly_hours
    if body.role == 'LEAD' and row.role != 'LEAD':
        make_lead(db, ctx, subject, row.user_id)
    record_audit(db, ctx, 'staff.allocation_updated', row.id, ctx.institution_id, body.role)
    commit(db)
    user = db.get(User, row.user_id)
    profile = scoped(db, StaffMember, ctx).filter_by(user_id=row.user_id).first()
    return allocation_view(row, subject, group, profile, user)


@router.delete('/management/allocations/{allocation_id}')
def delete_allocation(allocation_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row, subject, _ = owned_allocation(db, ctx, allocation_id)
    if row.role == 'LEAD' or subject.teacher_id == row.user_id and row.group_name == '':
        raise HTTPException(409, 'Make another teacher the lead before removing this one')
    db.delete(row)
    record_audit(db, ctx, 'staff.allocation_removed', allocation_id, ctx.institution_id, str(subject.id))
    commit(db)
    return dict(removed=True)


# --- Staff attendance ---------------------------------------------------------

@router.get('/management/attendance')
def attendance(day: date, department_id: uuid.UUID | None = None, category: Literal['TEACHING', 'NON_TEACHING'] | None = None,
               offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
               db: Session = Depends(get_db), ctx: AuthContext = Depends(require_permission('staff_attendance.manage'))):
    employees = scoped(db, StaffMember, ctx)
    # Include archived employees when they have a historical entry for this date.
    history = scoped(db, StaffAttendance, ctx).filter_by(day=day).with_entities(StaffAttendance.staff_id)
    employees = employees.filter(or_(StaffMember.status != 'INACTIVE', StaffMember.id.in_(history)))
    if department_id: employees = employees.filter_by(department_id=department_id)
    if category: employees = employees.filter_by(category=category)
    total = employees.count()
    page = employees.order_by(StaffMember.first_name, StaffMember.last_name, StaffMember.id).offset(offset).limit(limit).all()
    records = {r.staff_id: r for r in scoped(db, StaffAttendance, ctx).filter(StaffAttendance.day == day, StaffAttendance.staff_id.in_([s.id for s in page]))}
    return dict(day=day, total=total, items=[dict(staff=view(s), attendance=view(records[s.id]) if s.id in records else None) for s in page])


class AttendanceEntry(Input):
    staff_id: uuid.UUID
    status: Literal['PRESENT', 'ABSENT', 'LATE', 'LEAVE', 'OFF_DUTY']
    note: str = Field(default='', max_length=500)
    expected_updated_at: str | None = Field(default=None, max_length=60)


class AttendanceInput(Input):
    day: date
    entries: list[AttendanceEntry] = Field(min_length=1, max_length=200)

    @model_validator(mode='after')
    def unique_entries(self):
        if len({entry.staff_id for entry in self.entries}) != len(self.entries): raise ValueError('Each employee can appear only once')
        return self


@router.put('/management/attendance')
def save_attendance(body: AttendanceInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_permission('staff_attendance.manage'))):
    if body.day > kenya_today(): raise HTTPException(422, 'Attendance cannot be recorded for a future day')
    # Lock in a consistent order; all entries are validated before any are changed.
    pending = []
    for entry in sorted(body.entries, key=lambda e: str(e.staff_id)):
        employee = owned(db, StaffMember, entry.staff_id, ctx.institution_id, lock=True)
        row = scoped(db, StaffAttendance, ctx).filter_by(staff_id=employee.id, day=body.day).with_for_update().first()
        if row: unchanged(row, entry.expected_updated_at)
        elif entry.expected_updated_at is not None: raise HTTPException(409, 'Attendance changed. Reload the register.')
        if not row and employee.status == 'INACTIVE': raise HTTPException(409, 'Inactive employees cannot receive new attendance records')
        if employee.joined_on and body.day < employee.joined_on: raise HTTPException(422, 'Attendance cannot precede the employee joining date')
        pending.append((entry, row))
    for entry, row in pending:
        if row is None:
            row = StaffAttendance(institution_id=ctx.institution_id, staff_id=entry.staff_id, day=body.day)
            db.add(row)
        row.status, row.note = entry.status, entry.note
    record_audit(db, ctx, 'staff.attendance_saved', body.day.isoformat(), ctx.institution_id, f'{len(pending)} staff entries')
    commit(db)
    return dict(saved=len(pending))


@router.get('/management/overview')
def overview(db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    enabled = institution_modules(db.get(Institution, ctx.institution_id))
    staff_rows = scoped(db, StaffMember, ctx)
    active = staff_rows.filter_by(status='ACTIVE')
    attendance_rows = scoped(db, StaffAttendance, ctx).filter_by(day=kenya_today())
    return dict(staff_total=staff_rows.count(), active_staff=active.count(), teaching_staff=active.filter_by(category='TEACHING').count(),
        non_teaching_staff=active.filter_by(category='NON_TEACHING').count(), departments=scoped(db, Department, ctx).count(),
        active_allocations=allocation_rows(db, ctx).filter(AcademicClass.academic_year.not_in(closed_years(db, ctx))).count() if enabled['course_allocation'] else None,
        attendance_today=dict(attendance_rows.with_entities(StaffAttendance.status, func.count(StaffAttendance.id)).group_by(StaffAttendance.status).all()) if enabled['staff_attendance'] else None,
        modules=enabled)


@router.get('/teacher/staff-allocations')
def own_allocations(db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    require_enabled(db.get(Institution, ctx.institution_id), 'course_allocation')
    employee = scoped(db, StaffMember, ctx).filter_by(user_id=ctx.user_id).first()
    if not employee: return dict(employee=None, allocations=[])
    rows = allocation_rows(db, ctx).filter(OfferingTeacher.user_id == ctx.user_id).with_entities(*ALLOCATION_ENTITIES).order_by(
        AcademicClass.academic_year.desc(), Subject.name).all()
    return dict(employee=dict(staff_number=employee.staff_number, job_title=employee.job_title, status=employee.status),
        allocations=[allocation_view(*row) for row in rows])
