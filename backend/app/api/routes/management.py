"""Institution modules, employee directory, workload allocation and staff registers."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.core.deps import AuthContext, require_platform_admin, require_tenant_user
from app.db.session import get_db
from app.models.institution import Institution, InstitutionStatus
from app.models.user import User, UserRole, UserStatus
from app.models.curriculum import Department, CatalogueUnit
from app.models.management import StaffMember, StaffAllocation, StaffAttendance
from app.schemas.academic import Input
from app.services.modules import InstitutionModules, DEPENDENCIES, institution_modules, module_presets, require_enabled
from app.services.audit_service import record_audit
from app.services.subscriptions import kenya_today
from app.api.routes.teaching import admin, staff, scoped, commit

router = APIRouter(prefix='/api', tags=['Institution management'])


def view(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def owned(db, model, identity, tenant, lock=False):
    query = db.query(model).filter_by(id=identity, institution_id=tenant)
    row = (query.with_for_update() if lock else query).first()
    if not row: raise HTTPException(404, 'Management record not found')
    return row


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


class StaffInput(Input):
    staff_number: str = Field(min_length=1, max_length=40, pattern=r'^[A-Za-z0-9._/-]+$')
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    category: Literal['TEACHING', 'NON_TEACHING']
    job_title: str = Field(min_length=1, max_length=120)
    department_id: uuid.UUID | None = None
    teacher_user_id: uuid.UUID | None = None
    email: str | None = Field(default=None, max_length=255, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    phone: str | None = Field(default=None, max_length=50)
    employment_type: Literal['FULL_TIME', 'PART_TIME', 'CONTRACT', 'VOLUNTEER'] = 'FULL_TIME'
    status: Literal['ACTIVE', 'ON_LEAVE', 'INACTIVE'] = 'ACTIVE'
    joined_on: date | None = None
    expected_updated_at: str | None = Field(default=None, max_length=60)


def validate_staff(db, ctx, body, row=None):
    if body.department_id: owned(db, Department, body.department_id, ctx.institution_id)
    if body.teacher_user_id:
        account = owned(db, User, body.teacher_user_id, ctx.institution_id)
        linking_new_account = row is None or row.teacher_user_id != body.teacher_user_id
        if body.category != 'TEACHING' or account.role != UserRole.TEACHER or linking_new_account and account.status != UserStatus.ACTIVE:
            raise HTTPException(422, 'Only teaching staff can be linked to an active teacher account')
    if row and body.status != 'ACTIVE' and scoped(db, StaffAllocation, ctx).filter_by(staff_id=row.id, active=True).first():
        raise HTTPException(409, 'End active course allocations before placing this employee on leave or marking them inactive')
    if row and body.category != 'TEACHING' and scoped(db, StaffAllocation, ctx).filter_by(staff_id=row.id, active=True).first():
        raise HTTPException(409, 'End active teaching allocations before changing staff category')


class DepartmentInput(Input):
    code: str = Field(min_length=1, max_length=30, pattern=r'^[A-Za-z0-9._/-]+$')
    name: str = Field(min_length=1, max_length=160)
    expected_updated_at: str | None = Field(default=None, max_length=60)


@router.get('/management/departments')
def departments(db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    return [view(row) for row in scoped(db, Department, ctx).order_by(Department.name)]


@router.post('/management/departments', status_code=201)
def create_department(body: DepartmentInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = Department(id=uuid.uuid4(), institution_id=ctx.institution_id, code=body.code.upper(), name=body.name)
    db.add(row)
    record_audit(db, ctx, 'department.created', row.id, ctx.institution_id)
    commit(db)
    return view(row)


@router.put('/management/departments/{department_id}')
def edit_department(department_id: uuid.UUID, body: DepartmentInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = owned(db, Department, department_id, ctx.institution_id, lock=True)
    unchanged(row, body.expected_updated_at)
    row.code, row.name = body.code.upper(), body.name
    record_audit(db, ctx, 'department.updated', row.id, ctx.institution_id)
    commit(db)
    return view(row)


@router.get('/management/options')
def options(db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    enabled = institution_modules(db.get(Institution, ctx.institution_id))
    return dict(departments=[view(row) for row in scoped(db, Department, ctx).order_by(Department.name)],
        courses=[view(row) for row in scoped(db, CatalogueUnit, ctx).order_by(CatalogueUnit.code)] if enabled['course_allocation'] else [],
        teachers=[dict(id=row.id, name=f'{row.first_name} {row.last_name}', email=row.email, status=row.status)
                  for row in scoped(db, User, ctx).filter_by(role=UserRole.TEACHER).order_by(User.first_name)],
        staff=[dict(id=row.id, name=f'{row.first_name} {row.last_name}', staff_number=row.staff_number, category=row.category, status=row.status)
               for row in scoped(db, StaffMember, ctx).order_by(StaffMember.first_name)])


@router.get('/management/staff')
def staff_list(search: str = Query('', max_length=100), category: Literal['TEACHING', 'NON_TEACHING'] | None = None,
               status: Literal['ACTIVE', 'ON_LEAVE', 'INACTIVE'] | None = None, department_id: uuid.UUID | None = None,
               offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
               db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    query = scoped(db, StaffMember, ctx)
    if search:
        term = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(or_(*(column.ilike(term, escape='\\') for column in [StaffMember.staff_number, StaffMember.first_name, StaffMember.last_name, StaffMember.job_title])))
    if category: query = query.filter_by(category=category)
    if status: query = query.filter_by(status=status)
    if department_id: query = query.filter_by(department_id=department_id)
    return dict(total=query.count(), items=[view(row) for row in query.order_by(StaffMember.first_name, StaffMember.last_name, StaffMember.id).offset(offset).limit(limit)])


@router.post('/management/staff', status_code=201)
def create_staff(body: StaffInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    validate_staff(db, ctx, body)
    row = StaffMember(id=uuid.uuid4(), institution_id=ctx.institution_id, **body.model_dump(exclude={'expected_updated_at'}))
    row.staff_number = row.staff_number.upper()
    db.add(row)
    record_audit(db, ctx, 'staff.created', row.id, ctx.institution_id)
    commit(db)
    return view(row)


@router.put('/management/staff/{staff_id}')
def edit_staff(staff_id: uuid.UUID, body: StaffInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = owned(db, StaffMember, staff_id, ctx.institution_id, lock=True)
    unchanged(row, body.expected_updated_at)
    validate_staff(db, ctx, body, row)
    for key, value in body.model_dump(exclude={'expected_updated_at'}).items(): setattr(row, key, value)
    row.staff_number = row.staff_number.upper()
    record_audit(db, ctx, 'staff.updated', row.id, ctx.institution_id)
    commit(db)
    return view(row)


class AllocationInput(Input):
    staff_id: uuid.UUID
    course_id: uuid.UUID
    period: str = Field(min_length=1, max_length=100)
    group_name: str = Field(default='', max_length=100)
    weekly_hours: Decimal = Field(gt=0, le=168, max_digits=5, decimal_places=2)
    active: bool = True
    expected_updated_at: str | None = Field(default=None, max_length=60)


@router.get('/management/allocations')
def allocations(period: str = Query('', max_length=100), staff_id: uuid.UUID | None = None, active: bool | None = None,
                offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    query = scoped(db, StaffAllocation, ctx)
    if period: query = query.filter_by(period=period)
    if staff_id: query = query.filter_by(staff_id=staff_id)
    if active is not None: query = query.filter_by(active=active)
    return dict(total=query.count(), items=[view(row) for row in query.order_by(StaffAllocation.period.desc(), StaffAllocation.created_at.desc(), StaffAllocation.id).offset(offset).limit(limit)])


def write_allocation(db, ctx, body, row=None):
    employee = owned(db, StaffMember, body.staff_id, ctx.institution_id, lock=True)
    owned(db, CatalogueUnit, body.course_id, ctx.institution_id)
    if body.active and (employee.category != 'TEACHING' or employee.status != 'ACTIVE'):
        raise HTTPException(422, 'Active allocations require an active teaching employee')
    if body.active:
        workload = scoped(db, StaffAllocation, ctx).filter_by(staff_id=employee.id, period=body.period, active=True)
        if row: workload = workload.filter(StaffAllocation.id != row.id)
        total = workload.with_entities(func.coalesce(func.sum(StaffAllocation.weekly_hours), 0)).scalar()
        if total + body.weekly_hours > 168: raise HTTPException(422, 'Combined weekly hours in this period cannot exceed 168')
    if row:
        unchanged(row, body.expected_updated_at)
        for key, value in body.model_dump(exclude={'expected_updated_at'}).items(): setattr(row, key, value)
    else:
        row = StaffAllocation(id=uuid.uuid4(), institution_id=ctx.institution_id, **body.model_dump(exclude={'expected_updated_at'}))
        db.add(row)
    record_audit(db, ctx, 'staff.allocation_updated' if body.expected_updated_at else 'staff.allocation_created', row.id, ctx.institution_id)
    commit(db)
    return view(row)


@router.post('/management/allocations', status_code=201)
def create_allocation(body: AllocationInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    return write_allocation(db, ctx, body)


@router.put('/management/allocations/{allocation_id}')
def edit_allocation(allocation_id: uuid.UUID, body: AllocationInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = owned(db, StaffAllocation, allocation_id, ctx.institution_id, lock=True)
    return write_allocation(db, ctx, body, row)


@router.get('/management/attendance')
def attendance(day: date, department_id: uuid.UUID | None = None, category: Literal['TEACHING', 'NON_TEACHING'] | None = None,
               offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
               db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
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
def save_attendance(body: AttendanceInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
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
    staff = scoped(db, StaffMember, ctx)
    active = staff.filter_by(status='ACTIVE')
    allocation = scoped(db, StaffAllocation, ctx).filter_by(active=True)
    attendance = scoped(db, StaffAttendance, ctx).filter_by(day=kenya_today())
    return dict(staff_total=staff.count(), active_staff=active.count(), teaching_staff=active.filter_by(category='TEACHING').count(),
        non_teaching_staff=active.filter_by(category='NON_TEACHING').count(), departments=scoped(db, Department, ctx).count(),
        active_allocations=allocation.count() if enabled['course_allocation'] else None,
        attendance_today=dict(attendance.with_entities(StaffAttendance.status, func.count(StaffAttendance.id)).group_by(StaffAttendance.status).all()) if enabled['staff_attendance'] else None,
        modules=enabled)


@router.get('/teacher/staff-allocations')
def own_allocations(db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    require_enabled(db.get(Institution, ctx.institution_id), 'course_allocation')
    employee = scoped(db, StaffMember, ctx).filter_by(teacher_user_id=ctx.user_id).first()
    if not employee: return dict(employee=None, allocations=[])
    courses = scoped(db, StaffAllocation, ctx).join(CatalogueUnit, CatalogueUnit.id == StaffAllocation.course_id).filter(
        StaffAllocation.staff_id == employee.id).with_entities(StaffAllocation, CatalogueUnit).order_by(StaffAllocation.period.desc()).all()
    return dict(employee=dict(staff_number=employee.staff_number, job_title=employee.job_title, status=employee.status),
        allocations=[dict(**view(row), course_name=course.name, course_code=course.code) for row, course in courses])
