"""Signed, tenant-scoped exports and atomic merge recovery.

Full PostgreSQL recovery targets a separately configured empty database.
Archives are authenticated before any payload is interpreted or executed.
"""
import hashlib
import hmac
import io
import json
import os
import shutil
import subprocess
import tempfile
import uuid
import zipfile
import zlib
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.institution import Institution, InstitutionStatus
from app.models.user import User, UserRole
from app.models.teacher import Teacher
from app.models.academic import AcademicClass, Subject, Student, Enrollment, Coursework, Score, Attendance
from app.models.learning import CourseMaterial, Submission
from app.models.subscription import Subscription, SubscriptionPayment, BillingNotice
from app.models.verification_code import VerificationCode
from app.models.invitation import Invitation, InvitationStatus
from app.models.pilot import AcademicYear, AcademicPeriod
from app.models.curriculum import Department, Programme, StudyLevel, CatalogueUnit, CourseRegistration, CourseCompletion

from app.models.academic_document import AcademicDocument
from app.models.final_grade import FinalGrade
from app.models.progression import Prerequisite, ProgressionDecision

MAX_ARCHIVE = 512 * 1024 * 1024
MAX_INSTITUTION = 50 * 1024 * 1024
GROUPS = {"people": [User, Teacher, Student], "academics": [Department, Programme, StudyLevel, CatalogueUnit, Prerequisite, AcademicYear, AcademicPeriod, AcademicClass, Subject, Enrollment, CourseRegistration, CourseCompletion, ProgressionDecision],
          "learning": [Coursework, CourseMaterial, Score, Submission, FinalGrade, AcademicDocument], "attendance": [Attendance],
          "billing": [Subscription, SubscriptionPayment, BillingNotice]}
ORDER = [User, Teacher, Student, Department, Programme, StudyLevel, CatalogueUnit, Prerequisite, AcademicYear, AcademicPeriod, AcademicClass, Subject, Enrollment, CourseRegistration, CourseCompletion, ProgressionDecision, Coursework, CourseMaterial,
         Score, Submission, FinalGrade, AcademicDocument, Attendance, Subscription, SubscriptionPayment, BillingNotice]
MODELS = {model.__tablename__: model for model in ORDER}


def signing_key():
    key = settings.BACKUP_SIGNING_KEY or (settings.JWT_SECRET_KEY if settings.is_development else "")
    if not key:
        raise HTTPException(503, "Configure a dedicated backup signing key before using backup and restore.")
    return hashlib.sha256(("skynet-backup-v1:" + key).encode()).digest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def file_hash(value):
    if not isinstance(value, Path): return hashlib.sha256(value).hexdigest()
    digest = hashlib.sha256()
    with value.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def signed_manifest(digest, kind, **metadata):
    manifest = dict(format="skynet-backup-v1", kind=kind, created_at=datetime.now(timezone.utc).isoformat(), sha256=digest, **metadata)
    manifest["signature"] = hmac.new(signing_key(), canonical(manifest), hashlib.sha256).hexdigest()
    return manifest


def archive(payload, kind, **metadata):
    manifest = signed_manifest(file_hash(payload), kind, **metadata)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("manifest.json", canonical(manifest))
        zipped.writestr("data.dump" if kind == "platform" else "data.json", payload)
    return output.getvalue()


def open_archive(raw):
    temporary_payload = None
    try:
        if (raw.stat().st_size if isinstance(raw, Path) else len(raw)) > MAX_ARCHIVE:
            raise ValueError()
        with zipfile.ZipFile(raw if isinstance(raw, Path) else io.BytesIO(raw)) as zipped:
            if len(zipped.infolist()) != 2 or zipped.getinfo("manifest.json").file_size > 100000:
                raise ValueError()
            manifest = json.loads(zipped.read("manifest.json"))
            signature = manifest.pop("signature")
            expected = hmac.new(signing_key(), canonical(manifest), hashlib.sha256).hexdigest()
            if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
                raise ValueError()
            if manifest["format"] != "skynet-backup-v1" or manifest["kind"] not in {"institution", "platform"}:
                raise ValueError()
            name = "data.dump" if manifest["kind"] == "platform" else "data.json"
            if set(zipped.namelist()) != {"manifest.json", name} or zipped.getinfo(name).file_size > (MAX_ARCHIVE if name == "data.dump" else MAX_INSTITUTION):
                raise ValueError()
            if manifest["kind"] == "platform":
                with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as file:
                    temporary_payload = Path(file.name)
                    size = 0
                    with zipped.open(name) as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            size += len(chunk)
                            if size > MAX_ARCHIVE: raise ValueError()
                            file.write(chunk)
                payload = temporary_payload
            else:
                payload = zipped.read(name)
            if not hmac.compare_digest(file_hash(payload), manifest["sha256"]):
                raise ValueError()
        return manifest, payload
    except HTTPException:
        if temporary_payload: temporary_payload.unlink(missing_ok=True)
        raise
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, zipfile.BadZipFile, zlib.error, RuntimeError, RecursionError):
        if temporary_payload: temporary_payload.unlink(missing_ok=True)
        raise HTTPException(400, "Invalid, damaged or unauthenticated Skynet backup. Use an original signed export from this platform.")
    except OSError:
        if temporary_payload: temporary_payload.unlink(missing_ok=True)
        raise HTTPException(503, "Backup staging failed. Check available server storage.")


def row_dict(row):
    result = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, (datetime, date)): value = value.isoformat()
        elif isinstance(value, (uuid.UUID, Decimal)): value = str(value)
        elif hasattr(value, "value"): value = value.value
        result[column.name] = value
    if isinstance(row, Institution):
        result.pop("archived_by", None)
        result.pop("archived_at", None)
    return result


def export_institution(db, institution_id, groups):
    if not groups or set(groups) - GROUPS.keys():
        raise HTTPException(422, "Select valid backup data sets.")
    groups = sorted(set(groups) | {"people", "academics"})
    models = {model for group in groups for model in GROUPS[group]}
    # Export all tables from one repeatable-read snapshot, independent of auth reads.
    with db.get_bind().connect() as connection:
        if connection.dialect.name == "postgresql":
            connection = connection.execution_options(isolation_level="REPEATABLE READ")
        with Session(bind=connection) as snapshot:
            institution = snapshot.get(Institution, institution_id)
            if institution is None: raise HTTPException(404, "Institution not found")
            tables, size = {}, 0
            for model in ORDER:
                if model not in models: continue
                rows = []
                for row in snapshot.query(model).filter(model.institution_id == institution_id).order_by(model.id).yield_per(500):
                    data = row_dict(row)
                    size += len(canonical(data)) + 1
                    if size > MAX_INSTITUTION or len(rows) >= 200000:
                        raise HTTPException(413, "Institution export exceeds the supported size. Use a full platform backup.")
                    rows.append(data)
                tables[model.__tablename__] = rows
            if any(row["role"] == "PLATFORM_ADMIN" for row in tables["users"]):
                raise HTTPException(409, "An institution contains an invalid platform-admin membership. Correct it before export.")
            payload = canonical(dict(institution=row_dict(institution), tables=tables))
            if len(payload) > MAX_INSTITUTION: raise HTTPException(413, "Institution export exceeds the supported size. Use a full platform backup.")
            return archive(payload, "institution", institution_id=str(institution_id), institution_code=institution.code,
                           groups=groups, counts={key: len(rows) for key, rows in tables.items()})


def convert(model, raw):
    columns = {column.name: column for column in model.__table__.columns}
    if set(raw) - columns.keys(): raise ValueError("Unsupported columns")
    values = {}
    for name, value in raw.items():
        column = columns[name]
        if value is None:
            if not column.nullable: raise ValueError("Missing value")
            values[name] = None
            continue
        kind = column.type.python_type
        if kind == uuid.UUID: value = uuid.UUID(value)
        elif kind == datetime: value = datetime.fromisoformat(value)
        elif kind == date: value = date.fromisoformat(value)
        elif kind == Decimal: value = Decimal(value)
        elif name == 'rubric_labels' and isinstance(value, list) and len(value) <= 12 and all(isinstance(s, str) and 0 < len(s) <= 60 for s in value): pass
        elif name == 'grading_bands' and isinstance(value, list) and len(value) <= 20: pass
        elif hasattr(column.type, "enum_class") and column.type.enum_class: value = column.type.enum_class(value)
        elif not isinstance(value, kind): raise ValueError("Wrong value type")
        if isinstance(value, str) and getattr(column.type, "length", None) and len(value) > column.type.length: raise ValueError("Value too long")
        values[name] = value
    if "id" not in values: raise ValueError("Missing identity")
    return values


def institution_payload(manifest, payload):
    try:
        data = json.loads(payload)
        institution = convert(Institution, data["institution"])
        if str(institution["id"]) != manifest["institution_id"] or institution["code"] != manifest["institution_code"]: raise ValueError()
        tables = {}
        for table, rows in data["tables"].items():
            if table not in MODELS or not isinstance(rows, list) or len(rows) > 200000: raise ValueError()
            values = [convert(MODELS[table], row) for row in rows]
            if len({row["id"] for row in values}) != len(values): raise ValueError()
            if any(row["institution_id"] != institution["id"] for row in values): raise ValueError()
            tables[table] = values
        if "users" not in tables or any(row["role"] == UserRole.PLATFORM_ADMIN for row in tables["users"]): raise ValueError()
        return institution, tables
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        raise HTTPException(400, "The backup contains unsupported or inconsistent institution data.")


def merge_fingerprint(db, institution_id, tables, lock=False):
    state = []
    for model in [Institution, *ORDER]:
        if model != Institution and model.__tablename__ not in tables: continue
        query = db.query(model).filter(model.id == institution_id) if model == Institution else db.query(model).filter(model.institution_id == institution_id)
        if lock: query = query.with_for_update()
        state.extend((model.__tablename__, str(row.id), row.updated_at.isoformat()) for row in query.order_by(model.id).all())
    return hashlib.sha256(canonical(state)).hexdigest()


def merge_institution(db, manifest, payload, expected_fingerprint):
    institution, tables = institution_payload(manifest, payload)
    tenant = institution["id"]
    if merge_fingerprint(db, tenant, tables, lock=True) != expected_fingerprint:
        raise HTTPException(409, "Institution data changed after the restore preview. Preview the backup again.")
    current = db.get(Institution, tenant)
    if current and (current.code != institution["code"] or current.status == InstitutionStatus.ARCHIVED):
        raise HTTPException(409, "Institution identity changed or is archived. Restore cannot change lifecycle controls.")
    if current is None:
        values = {key: value for key, value in institution.items() if key not in {"status"}}
        current = Institution(**values, status=institution.get("status", InstitutionStatus.ACTIVE))
        db.add(current)
    else:
        for key in ["name", "type", "country", "address", "official_email", "phone", "website", "learning_settings", "academic_configuration"]:
            if key in institution: setattr(current, key, institution[key])
    db.flush()
    for model in ORDER:
        for values in tables.get(model.__tablename__, []):
            if model == Teacher and values.get("invited_from"):
                invitation = db.query(Invitation).filter(Invitation.id == values["invited_from"], Invitation.institution_id == tenant).first()
                if invitation is None: values["invited_from"] = None
            row = db.get(model, values["id"])
            if row and row.institution_id != tenant:
                raise HTTPException(409, "Backup record conflicts with another institution.")
            if model == ProgressionDecision and row:
                if any(getattr(row, key) != values[key] for key in ['snapshot', 'student_id', 'source_class_id', 'target_class_id', 'decision']):
                    raise HTTPException(409, 'A progression decision differs from its stored history.')
                continue
            if model == AcademicDocument and row:
                if any(getattr(row, key) != values[key] for key in ['snapshot', 'reference', 'student_id', 'kind', 'source_digest', 'issued_by_name']):
                    raise HTTPException(409, 'An issued academic document differs from its stored history.')
                # Restoring an older archive must never reactivate a revoked document.
                if row.status == 'REVOKED': continue
            if model == SubscriptionPayment and row:
                if any(getattr(row, key) != values[key] for key in ["amount", "reference", "paid_on", "previous_due_date", "next_due_date", "recorded_by"]):
                    raise HTTPException(409, "A payment differs from the existing ledger. Financial history cannot be overwritten.")
                continue
            if row is None:
                row = model(**values)
                db.add(row)
            else:
                for key, value in values.items():
                    if key not in {"id", "institution_id"}: setattr(row, key, value)
        db.flush()
    revoke_recovered_access(db, tenant)
    # Caller commits the merge and its real-actor audit event together.
    return tenant


def revoke_recovered_access(connection, tenant=None):
    now = datetime.now(timezone.utc)
    users = select(User.id)
    user_update = User.__table__.update()
    invitations = Invitation.__table__.update().where(Invitation.status.in_([InvitationStatus.SENT, InvitationStatus.SUBMITTED]))
    if tenant is not None:
        users = users.where(User.institution_id == tenant)
        user_update = user_update.where(User.institution_id == tenant)
        invitations = invitations.where(Invitation.institution_id == tenant)
    connection.execute(user_update.values(password_changed_at=now, updated_at=now))
    connection.execute(VerificationCode.__table__.update().where(VerificationCode.user_id.in_(users), VerificationCode.consumed_at.is_(None)).values(consumed_at=now, expires_at=now))
    connection.execute(invitations.values(status=InvitationStatus.EXPIRED, expires_at=now))


def postgres_tool(name):
    configured = settings.PG_DUMP_PATH if name == "pg_dump" else settings.PG_RESTORE_PATH
    found = configured or shutil.which(name)
    if not found and os.name == "nt":
        candidate = Path(f"C:/Program Files/PostgreSQL/18/bin/{name}.exe")
        if candidate.is_file(): found = str(candidate)
    return found


def pg_environment(url):
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql": raise HTTPException(503, "PostgreSQL is required for full platform backups.")
    env = {**os.environ, "PGHOST": parsed.host or "localhost", "PGPORT": str(parsed.port or 5432), "PGUSER": parsed.username or "",
           "PGPASSWORD": parsed.password or "", "PGDATABASE": parsed.database or "", "PGCONNECT_TIMEOUT": "15"}
    env["PGSSLMODE"] = parsed.query.get("sslmode", "prefer" if parsed.host in {"localhost", "127.0.0.1", "::1"} else "require")
    return env


def run_postgres(command, url):
    try:
        result = subprocess.run(command, env=pg_environment(url), capture_output=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode: raise HTTPException(503, "PostgreSQL backup/recovery failed. Check the server tool version, permissions and connection settings.")
    except (OSError, subprocess.TimeoutExpired):
        raise HTTPException(503, "PostgreSQL backup/recovery tools are unavailable or timed out.")


def full_backup():
    tool = postgres_tool("pg_dump")
    if not tool: raise HTTPException(503, "Install/configure pg_dump on the API server to enable full backups.")
    signing_key()
    path, output = None, None
    try:
        with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as file: path = Path(file.name)
        run_postgres([tool, "--format=custom", "--no-owner", "--no-acl", "--lock-wait-timeout=10000", "--file", str(path)], settings.DATABASE_URL_UNPOOLED or settings.DATABASE_URL)
        if path.stat().st_size > MAX_ARCHIVE: raise HTTPException(413, "Database exceeds the web export size limit. Use managed database backup tooling.")
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as file: output = Path(file.name)
        # A custom-format PostgreSQL dump is already compressed. Store it without
        # recompressing or loading the whole snapshot into application memory.
        with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as zipped:
            zipped.writestr("manifest.json", canonical(signed_manifest(file_hash(path), "platform")))
            zipped.write(path, "data.dump")
        if output.stat().st_size > MAX_ARCHIVE: raise HTTPException(413, "Database archive exceeds the web export size limit.")
        return output
    except Exception:
        if output: output.unlink(missing_ok=True)
        raise
    finally:
        if path: path.unlink(missing_ok=True)


def recovery_engine():
    if not settings.RESTORE_DATABASE_URL: raise HTTPException(503, "Configure a separate empty recovery database before full-platform restore.")
    source, target = make_url(settings.DATABASE_URL), make_url(settings.RESTORE_DATABASE_URL)
    if target.get_backend_name() != "postgresql" or (source.host, source.port or 5432, source.database) == (target.host, target.port or 5432, target.database):
        raise HTTPException(409, "Full recovery must use a different database from the running platform.")
    # Prevent pooled/direct aliases of the same Neon database from bypassing the check.
    if (source.host or "").replace("-pooler", "") == (target.host or "").replace("-pooler", "") and source.database == target.database:
        raise HTTPException(409, "Recovery cannot target the running database.")
    engine = create_engine(settings.RESTORE_DATABASE_URL, connect_args={"connect_timeout": 15})
    try:
        if inspect(engine).get_table_names(schema="public") or inspect(engine).get_view_names(schema="public"):
            raise HTTPException(409, "Recovery database is not empty. Use an empty recovery database.")
        return engine
    except Exception:
        engine.dispose()
        raise


def restore_platform(payload):
    tool = postgres_tool("pg_restore")
    if not tool: raise HTTPException(503, "Install/configure pg_restore on the API server to enable recovery.")
    engine = recovery_engine()
    path = payload if isinstance(payload, Path) else None
    owns_path = path is None
    try:
        if owns_path:
            with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as file:
                path = Path(file.name); file.write(payload)
        run_postgres([tool, "--dbname", make_url(settings.RESTORE_DATABASE_URL).database,
                      "--no-owner", "--no-acl", "--single-transaction", "--exit-on-error", str(path)], settings.RESTORE_DATABASE_URL)
        with engine.begin() as connection:
            revoke_recovered_access(connection)
    finally:
        engine.dispose()
        if path and owns_path: path.unlink(missing_ok=True)
