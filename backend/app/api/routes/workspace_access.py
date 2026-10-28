import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, get_current_context
from app.core.security import create_workspace_token
from app.core.workspace_access import resolve_workspace_target
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserSummary
from app.services.audit_service import record_audit

router = APIRouter(prefix="/api/workspace-access", tags=["Workspace access"])


class WorkspaceStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_user_id: uuid.UUID


@router.post("/start")
def start_workspace(body: WorkspaceStart, db: Session = Depends(get_db), ctx: AuthContext = Depends(get_current_context)):
    actor = db.get(User, ctx.actor_user_id or ctx.user_id)
    target, read_only = resolve_workspace_target(db, actor, body.target_user_id)
    record_audit(db, ctx, "workspace.entered", target.id, target.institution_id,
                 "Read-only" if read_only else "Full access")
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
