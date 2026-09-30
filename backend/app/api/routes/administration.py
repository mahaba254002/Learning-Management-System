"""Institution-scoped operations and explicit platform oversight."""
import uuid
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, HttpUrl
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.core.deps import AuthContext, require_platform_admin, require_role
from app.db.session import get_db
from app.models.academic import AcademicClass, Attendance, Coursework, Enrollment, Score, Student, Subject
from app.models.audit import AuditEvent
from app.models.institution import Institution, InstitutionStatus
from app.models.invitation import Invitation, InvitationStatus
from app.models.learning import Submission
from app.models.user import User, UserRole, UserStatus
from app.schemas.academic import Input
from app.services.audit_service import record_audit
from app.api.routes.teaching import commit

router = APIRouter(prefix='/api', tags=['Administration'])
institution_admin = require_role(UserRole.INSTITUTION_ADMIN)


class InstitutionSettings(Input):
    name: str = Field(min_length=1, max_length=255)
    country: str = Field(min_length=1, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    official_email: str | None = Field(default=None, max_length=255, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    phone: str | None = Field(default=None, max_length=50)
    website: HttpUrl | None = Field(default=None, max_length=255)


class StatusInput(Input):
    status: Literal['ACTIVE', 'SUSPENDED']


def institution_view(row):
    return {key: getattr(row, key) for key in ('id', 'name', 'code', 'type', 'country', 'address', 'official_email', 'phone', 'website', 'status')}


@router.get('/institution/settings')
def get_settings(db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    return institution_view(db.get(Institution, ctx.institution_id))


@router.put('/institution/settings')
def save_settings(body: InstitutionSettings, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    row = db.get(Institution, ctx.institution_id)
    for key, value in body.model_dump(mode='json').items(): setattr(row, key, value)
    record_audit(db, ctx, 'institution.settings_updated', row.id, row.id)
    commit(db)
    return institution_view(row)


@router.get('/institution/overview')
def overview(db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    def count(model): return db.query(model).filter(model.institution_id == ctx.institution_id).count()
    role_counts = dict(db.query(User.role, func.count(User.id)).filter(User.institution_id == ctx.institution_id).group_by(User.role).all())
    pending = db.query(Invitation).filter(Invitation.institution_id == ctx.institution_id, Invitation.status == InvitationStatus.SUBMITTED).count()
    attendance = dict(db.query(Attendance.status, func.count(Attendance.id)).filter(Attendance.institution_id == ctx.institution_id).group_by(Attendance.status).all())
    return dict(institution=institution_view(db.get(Institution, ctx.institution_id)), users_by_role=role_counts,
        classes=count(AcademicClass), subjects=count(Subject), students=count(Student), assessments=count(Coursework),
        pending_invitations=pending, attendance=attendance,
        active_enrollments=db.query(Enrollment).filter(Enrollment.institution_id == ctx.institution_id, Enrollment.active.is_(True)).count(),
        final_submissions=db.query(Submission).filter(Submission.institution_id == ctx.institution_id, Submission.status == 'SUBMITTED').count(),
        scores_recorded=count(Score))


def user_page(db, tenant=None, search='', role=None, offset=0, limit=50):
    q = db.query(User)
    if tenant is not None: q = q.filter(User.institution_id == tenant)
    if role is not None: q = q.filter(User.role == role)
    if search:
        term = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        q = q.filter(or_(User.first_name.ilike(term, escape='\\'), User.last_name.ilike(term, escape='\\'), User.username.ilike(term, escape='\\')))
    total = q.count()
    rows = q.order_by(User.created_at.desc(), User.id).offset(offset).limit(limit).all()
    return dict(total=total, items=[dict(id=u.id, institution_id=u.institution_id, first_name=u.first_name, last_name=u.last_name,
        username=u.username, email=u.email, role=u.role, status=u.status, must_change_password=u.must_change_password) for u in rows])


@router.get('/institution/users')
def institution_users(search: str = Query('', max_length=100), role: UserRole | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    return user_page(db, ctx.institution_id, search, role, offset, limit)


@router.get('/platform/users')
def platform_users(search: str = Query('', max_length=100), role: UserRole | None = None, institution_id: uuid.UUID | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    return user_page(db, institution_id, search, role, offset, limit)


def change_user_status(db, ctx, user_id, body, platform=False):
    q = db.query(User).filter(User.id == user_id)
    if not platform: q = q.filter(User.institution_id == ctx.institution_id)
    row = q.with_for_update().first()
    if not row: raise HTTPException(404, 'User not found')
    # Platform accounts and institution-admin peers cannot be disabled here.
    allowed = {UserRole.TEACHER, UserRole.STUDENT, UserRole.INSTITUTION_ADMIN} if platform else {UserRole.TEACHER, UserRole.STUDENT}
    if row.id == ctx.user_id or row.role not in allowed: raise HTTPException(403, 'This account cannot be changed here')
    if row.status == UserStatus.INVITED: raise HTTPException(409, 'Complete the invitation process first')
    if row.status.value != body.status:
        row.status = UserStatus(body.status)
        # Invalidate earlier sessions so reactivation does not revive old cookies.
        row.password_changed_at = datetime.now(timezone.utc)
        record_audit(db, ctx, 'user.status_changed', row.id, row.institution_id, body.status)
        commit(db)
    return dict(id=row.id, status=row.status)


@router.put('/institution/users/{user_id}/status')
def institution_user_status(user_id: uuid.UUID, body: StatusInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    return change_user_status(db, ctx, user_id, body)


@router.put('/platform/users/{user_id}/status')
def platform_user_status(user_id: uuid.UUID, body: StatusInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    return change_user_status(db, ctx, user_id, body, platform=True)


@router.put('/platform/institutions/{institution_id}/status')
def institution_status(institution_id: uuid.UUID, body: StatusInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    row = db.query(Institution).filter(Institution.id == institution_id).with_for_update().first()
    if not row: raise HTTPException(404, 'Institution not found')
    if row.status == InstitutionStatus.ARCHIVED: raise HTTPException(409, 'Archived institutions cannot be changed through suspension controls')
    if row.status.value != body.status:
        row.status = InstitutionStatus(body.status)
        db.query(User).filter(User.institution_id == row.id).update({User.password_changed_at: datetime.now(timezone.utc)}, synchronize_session='fetch')
        record_audit(db, ctx, 'institution.status_changed', row.id, row.id, body.status)
        commit(db)
    return institution_view(row)


def audit_page(db, tenant=None, offset=0, limit=50):
    q = db.query(AuditEvent)
    if tenant is not None: q = q.filter(AuditEvent.institution_id == tenant)
    return dict(total=q.count(), items=[dict(id=r.id, actor_id=r.actor_id, institution_id=r.institution_id,
        action=r.action, target_id=r.target_id, detail=r.detail, created_at=r.created_at)
        for r in q.order_by(AuditEvent.created_at.desc(), AuditEvent.id).offset(offset).limit(limit).all()])


@router.get('/institution/audit-logs')
def institution_audit(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    return audit_page(db, ctx.institution_id, offset, limit)


@router.get('/platform/audit-logs')
def platform_audit(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    return audit_page(db, offset=offset, limit=limit)


@router.get('/platform/usage')
def usage(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    return {label: db.query(model).count() for label, model in [('institutions', Institution), ('users', User), ('classes', AcademicClass), ('subjects', Subject), ('students', Student), ('assessments', Coursework)]}
