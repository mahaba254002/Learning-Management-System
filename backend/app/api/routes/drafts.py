"""Private recoverable work. Drafts never publish learning records."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import AuthContext, get_current_context
from app.db.session import get_db
from app.models.pilot import WorkDraft
from app.models.user import UserRole
from app.schemas.academic import Input
from app.core.rate_limit import rate_limit
from app.api.routes.teaching import get_class, get_coursework, get_subject, commit

router = APIRouter(prefix='/api/drafts', tags=['Work recovery'])
Kind = Literal['attendance', 'scores', 'assessment', 'submission']


class DraftInput(Input):
    data: dict
    expected_version: int = Field(ge=0)


def authorize(db, ctx, kind, resource):
    if len(resource) > 100: raise HTTPException(422, 'Invalid draft reference')
    try:
        parts = resource.split(':')
        identity = uuid.UUID(parts[0])
        if kind == 'attendance':
            if len(parts) not in {2, 3}: raise ValueError()
            date.fromisoformat(parts[1])
            subject = uuid.UUID(parts[2]) if len(parts) == 3 else None
        elif kind == 'assessment':
            if len(parts) != 2: raise ValueError()
            if parts[1] != 'new': uuid.UUID(parts[1])
        elif len(parts) != 1: raise ValueError()
    except ValueError:
        raise HTTPException(422, 'Invalid draft reference')
    if kind == 'submission':
        if ctx.role != UserRole.STUDENT: raise HTTPException(403, 'Student access required')
        from app.api.routes.learning import own_student, student_work
        student_work(db, identity, own_student(db, ctx), ctx, lock=ctx.request_method == 'PUT')
    else:
        if ctx.role not in {UserRole.TEACHER, UserRole.INSTITUTION_ADMIN}: raise HTTPException(403, 'Staff access required')
        if kind == 'attendance':
            from app.api.routes.teaching import attendance_scope
            attendance_scope(db, identity, subject, ctx)
        elif kind == 'scores': get_coursework(db, identity, ctx)
        else:
            get_subject(db, identity, ctx)
            if parts[1] != 'new':
                work, _ = get_coursework(db, uuid.UUID(parts[1]), ctx)
                if work.subject_id != identity: raise HTTPException(404, 'Assessment not found')


def check_identity(request, ctx):
    if request.headers.get('X-Draft-User') != str(ctx.user_id) or request.headers.get('X-Draft-Actor') != str(ctx.actor_user_id or ctx.user_id):
        raise HTTPException(409, 'Workspace changed. Return to the original account to recover this draft.')


def query(db, ctx, kind, resource):
    return db.query(WorkDraft).filter_by(actor_id=ctx.actor_user_id or ctx.user_id, user_id=ctx.user_id, kind=kind, resource=resource)


@router.get('/{kind}/{resource}')
def get_draft(request: Request, kind: Kind, resource: str, db: Session = Depends(get_db), ctx: AuthContext = Depends(get_current_context)):
    check_identity(request, ctx)
    authorize(db, ctx, kind, resource)
    row = query(db, ctx, kind, resource).first()
    if row and row.updated_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc) - timedelta(days=30):
        db.delete(row); db.commit(); row = None
    return dict(data=row.data, version=row.version, updated_at=row.updated_at) if row else dict(data=None, version=0)


@router.put('/{kind}/{resource}', dependencies=[Depends(rate_limit(max_requests=600, window_seconds=60, key_prefix='work-draft'))])
def save_draft(request: Request, kind: Kind, resource: str, body: DraftInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(get_current_context)):
    check_identity(request, ctx)
    authorize(db, ctx, kind, resource)
    if len(json.dumps(body.data).encode()) > 250000: raise HTTPException(413, 'Draft is too large')
    row = query(db, ctx, kind, resource).with_for_update().first()
    if body.expected_version != (row.version if row else 0):
        raise HTTPException(409, 'This recovery draft changed in another tab. Reload before editing it.')
    if not row:
        if db.query(WorkDraft.id).filter_by(actor_id=ctx.actor_user_id or ctx.user_id).count() >= 5000:
            raise HTTPException(409, 'Recovery draft limit reached. Contact your administrator.')
        row = WorkDraft(actor_id=ctx.actor_user_id or ctx.user_id, user_id=ctx.user_id, kind=kind, resource=resource, version=0)
        db.add(row)
    row.data, row.version = body.data, row.version + 1
    commit(db)
    return dict(version=row.version, updated_at=row.updated_at)
