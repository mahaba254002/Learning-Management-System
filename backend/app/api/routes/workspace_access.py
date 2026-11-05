import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, get_current_context
from app.core.security import create_workspace_token
from app.core.workspace_access import resolve_workspace_target
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import UserSummary
from app.services.audit_service import record_audit

router = APIRouter(prefix="/api/workspace-access", tags=["Workspace access"])


class WorkspaceStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_user_id: uuid.UUID
    # Platform admins open workspaces with full access, so they must say why.
    # The reason is stored in the audit log the institution can read.
    reason: str | None = Field(default=None, max_length=300)


MIN_REASON_LENGTH = 10


@router.post("/start")
def start_workspace(body: WorkspaceStart, db: Session = Depends(get_db), ctx: AuthContext = Depends(get_current_context)):
    actor = db.get(User, ctx.actor_user_id or ctx.user_id)
    reason = (body.reason or "").strip()
    if actor.role == UserRole.PLATFORM_ADMIN and len(reason) < MIN_REASON_LENGTH:
        raise HTTPException(422, f"Give a reason of at least {MIN_REASON_LENGTH} characters for opening this workspace.")
    target, read_only = resolve_workspace_target(db, actor, body.target_user_id)
    access = "Read-only" if read_only else "Full access"
    record_audit(db, ctx, "workspace.entered", target.id, target.institution_id,
                 f"{access}. Reason: {reason}" if reason else access)
    db.commit()
    effective = UserSummary.model_validate(target).model_copy(update={"must_change_password": False})
    return dict(token=create_workspace_token(actor_id=actor.id, target_id=target.id),
                user=effective, actor=UserSummary.model_validate(actor), read_only=read_only)


@router.post("/stop")
def stop_workspace(db: Session = Depends(get_db), ctx: AuthContext = Depends(get_current_context)):
    if ctx.actor_user_id is None:
        raise HTTPException(400, "No delegated workspace is open")
    record_audit(db, ctx, "workspace.exited", ctx.user_id, ctx.institution_id)
    db.commit()
    return UserSummary.model_validate(db.get(User, ctx.actor_user_id))
