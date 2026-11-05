"""Finer rights for non-teaching staff. Institution admins hold every right."""
from fastapi import Depends, HTTPException

from app.core.deps import AuthContext, require_tenant_user
from app.db.session import get_db
from app.models.management import StaffMember
from app.models.structure import STAFF_PERMISSIONS, StaffPermission
from app.models.user import UserRole


def granted_permissions(db, institution_id, user_id):
    # Rights only apply while the person's staff record is active.
    active = db.query(StaffMember.id).filter_by(institution_id=institution_id, user_id=user_id, status='ACTIVE').first()
    if not active: return set()
    return {p for (p,) in db.query(StaffPermission.permission).filter_by(institution_id=institution_id, user_id=user_id).all()}


def require_permission(*permissions):
    """Allow institution admins, and staff holding any one of these rights."""
    assert permissions and set(permissions) <= set(STAFF_PERMISSIONS), permissions

    def check(db=Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)) -> AuthContext:
        if ctx.role == UserRole.INSTITUTION_ADMIN:
            return ctx
        if ctx.role == UserRole.STAFF and set(permissions) & granted_permissions(db, ctx.institution_id, ctx.user_id):
            return ctx
        raise HTTPException(403, 'You do not have permission to perform this action')

    return check
