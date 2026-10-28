import uuid
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import AuthContext, require_platform_admin
from app.core.rate_limit import rate_limit
from app.core.security import decode_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.models.institution import Institution
from app.schemas.academic import Input
from app.services import backups
from app.services.audit_service import record_audit

router = APIRouter(prefix="/api/platform/backups", tags=["Backup and recovery"])


class BackupFileResponse(FileResponse):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            Path(self.path).unlink(missing_ok=True)


class ExportInput(Input):
    institution_id: uuid.UUID
    groups: list[str] = Field(min_length=1, max_length=5)


class AuthorizeInput(Input):
    plan_token: str = Field(max_length=10000)
    password: str = Field(min_length=1, max_length=1024)
    confirmation: str = Field(max_length=100)
    # Password whitespace is significant.
    model_config = {"extra": "forbid", "str_strip_whitespace": False}


def signed_token(data, actor, kind, minutes=10):
    now = datetime.now(timezone.utc)
    return jwt.encode({**data, "sub": str(actor), "type": kind, "iat": now.timestamp(), "exp": now + timedelta(minutes=minutes)},
                      settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def validate_token(token, actor, kind):
    try:
        data = decode_token(token)
        if data.get("sub") != str(actor) or data.get("type") != kind: raise ValueError()
        return data
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, "Restore review expired or is invalid. Preview the backup again.")


@router.get("/capabilities")
def capabilities(ctx: AuthContext = Depends(require_platform_admin)):
    key_available = bool(settings.BACKUP_SIGNING_KEY or settings.is_development)
    return dict(groups=list(backups.GROUPS), max_upload_bytes=backups.MAX_ARCHIVE,
                institution_backup=key_available, full_backup=key_available and bool(backups.postgres_tool("pg_dump")),
                full_restore=key_available and bool(backups.postgres_tool("pg_restore")) and bool(settings.RESTORE_DATABASE_URL))


def download(raw, filename):
    return Response(raw, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@router.post("/institution", dependencies=[Depends(rate_limit(max_requests=5, window_seconds=300, key_prefix="backup-export"))])
def institution_backup(body: ExportInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    raw = backups.export_institution(db, body.institution_id, body.groups)
    record_audit(db, ctx, "backup.institution_exported", body.institution_id, body.institution_id, ", ".join(sorted(set(body.groups))))
    db.commit()
    return download(raw, f"skynet-institution-{body.institution_id}.zip")


@router.post("/platform", dependencies=[Depends(rate_limit(max_requests=2, window_seconds=300, key_prefix="backup-full"))])
def platform_backup(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    path = backups.full_backup()
    try:
        record_audit(db, ctx, "backup.platform_exported", "platform", detail="Signed PostgreSQL snapshot generated")
        db.commit()
        return BackupFileResponse(path, media_type="application/zip", filename="skynet-platform-backup.zip", headers={"Cache-Control": "no-store"})
    except Exception:
        path.unlink(missing_ok=True)
        raise


async def read_upload(request):
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as file:
            path = Path(file.name)
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > backups.MAX_ARCHIVE: raise HTTPException(413, "Backup file exceeds the upload limit.")
                await run_in_threadpool(file.write, chunk)
        if not size: raise HTTPException(400, "Choose a backup file.")
        return path
    except BaseException:
        if path: path.unlink(missing_ok=True)
        raise


def preview(raw, db, ctx):
    manifest, payload = backups.open_archive(raw)
    try:
        return preview_manifest(raw, manifest, payload, db, ctx)
    finally:
        if isinstance(payload, Path): payload.unlink(missing_ok=True)


def preview_manifest(raw, manifest, payload, db, ctx):
    plan = dict(file_hash=backups.file_hash(raw), kind=manifest["kind"])
    if manifest["kind"] == "institution":
        institution, tables = backups.institution_payload(manifest, payload)
        target = db.get(Institution, institution["id"])
        if target and (target.code != institution["code"] or target.status.value == "ARCHIVED"):
            raise HTTPException(409, "The institution changed identity or is archived; merge recovery is not available.")
        plan.update(institution_id=str(institution["id"]), confirmation=f"RESTORE {institution['code']}",
                    fingerprint=backups.merge_fingerprint(db, institution["id"], tables))
        counts = {name: len(rows) for name, rows in tables.items()}
        label = institution["name"]
        mode = "Merge backed-up records; newer matching records may be replaced. Records absent from the backup are kept. Existing institution sessions and pending access links are revoked."
    else:
        engine = backups.recovery_engine(); engine.dispose()
        if not backups.postgres_tool("pg_restore"): raise HTTPException(503, "Configure pg_restore before full recovery.")
        plan["confirmation"] = "RESTORE PLATFORM"
        counts, label = {}, "Separate empty recovery database"
        mode = "Restore the full snapshot into the configured recovery database. The running database is unchanged; switch connections only after verification."
    return dict(kind=plan["kind"], created_at=manifest["created_at"], destination=label, mode=mode, counts=counts,
                confirmation=plan["confirmation"], plan_token=signed_token(plan, ctx.user_id, "restore-plan"))


@router.post("/restore/preview", dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, key_prefix="restore-preview"))])
async def restore_preview(request: Request, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    raw = await read_upload(request)
    try:
        return await run_in_threadpool(preview, raw, db, ctx)
    finally:
        raw.unlink(missing_ok=True)


@router.post("/restore/authorize", dependencies=[Depends(rate_limit(max_requests=5, window_seconds=300, key_prefix="restore-authorize"))])
def authorize_restore(body: AuthorizeInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    plan = validate_token(body.plan_token, ctx.user_id, "restore-plan")
    actor = db.get(User, ctx.user_id)
    if not verify_password(body.password, actor.password_hash): raise HTTPException(401, "The current administrator password is incorrect.")
    if body.confirmation != plan["confirmation"]: raise HTTPException(422, "The restore confirmation does not match.")
    return {"restore_token": signed_token(plan, ctx.user_id, "restore-execute", minutes=10)}


def execute_restore(raw, token, db, ctx):
    plan = validate_token(token, ctx.user_id, "restore-execute")
    if not backups.file_hash(raw) == plan["file_hash"]: raise HTTPException(409, "Backup file changed after review. Preview it again.")
    manifest, payload = backups.open_archive(raw)
    try:
        if manifest["kind"] == "institution":
            tenant = backups.merge_institution(db, manifest, payload, plan["fingerprint"])
            record_audit(db, ctx, "backup.institution_restored", tenant, tenant, "Atomic merge; existing institution sessions revoked")
        else:
            backups.restore_platform(payload)
            record_audit(db, ctx, "backup.platform_restored", "recovery-database", detail="Restored into separate recovery database; live connection unchanged")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Restore conflicts with existing identities or academic relationships. No institution records were changed.")
    except Exception:
        db.rollback()
        raise
    finally:
        if isinstance(payload, Path): payload.unlink(missing_ok=True)
    return {"message": "Institution records restored and sessions revoked." if manifest["kind"] == "institution" else "Snapshot restored to the recovery database. Verify it before switching the platform connection."}


@router.post("/restore/execute", dependencies=[Depends(rate_limit(max_requests=2, window_seconds=300, key_prefix="restore-execute"))])
async def restore_execute(request: Request, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    token = request.headers.get("X-Restore-Token", "")
    validate_token(token, ctx.user_id, "restore-execute")
    raw = await read_upload(request)
    try:
        return await run_in_threadpool(execute_restore, raw, token, db, ctx)
    finally:
        raw.unlink(missing_ok=True)
