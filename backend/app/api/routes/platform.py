"""
Platform-admin-only routes — actions that operate across every institution.
Kept in their own file/prefix (/api/platform/...) so it's visually obvious
which endpoints are intentionally cross-tenant, versus institution-scoped
routes elsewhere that use require_tenant_user instead.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.deps import AuthContext, require_platform_admin
from app.core.rate_limit import rate_limit
from app.core.verification import VerificationError, confirm_verification_code, generate_verification_code
from app.db.session import get_db
from app.models.institution import Institution, InstitutionStatus
from app.models.user import User
from app.models.verification_code import VerificationPurpose
from app.schemas.institution import (
    ConfirmCodeRequest,
    InstitutionCreateRequest,
    InstitutionResponse,
    PlatformStats,
    VerificationRequiredResponse,
)

from app.core.rate_limit import rate_limit
from app.models.user import User, UserRole, UserStatus
from app.schemas.institution import InstitutionAdminCreateRequest, InstitutionAdminCreatedResponse
from app.services.password_service import generate_temporary_password
from app.services.username_service import generate_username
router = APIRouter(prefix="/api/platform", tags=["platform-admin"])


# ---------------------------------------------------------------------------
# Create institution (step-up verified: request -> email code -> confirm)
# ---------------------------------------------------------------------------


@router.post(
    "/institutions/request-create",
    response_model=VerificationRequiredResponse,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=300, key_prefix="inst-request-create"))],
)
def request_create_institution(
    payload: InstitutionCreateRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_platform_admin),
) -> VerificationRequiredResponse:
    # Validate early so the admin isn't asked to check email for a request
    # that would fail anyway on confirm.
    existing = db.query(Institution).filter(Institution.code == payload.code).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Institution code '{payload.code}' is already taken",
        )

    admin = db.get(User, ctx.user_id)

    try:
        verification_id = generate_verification_code(
            db=db,
            user_id=ctx.user_id,
            user_email=admin.email if admin else None,
            purpose=VerificationPurpose.CREATE_INSTITUTION,
            payload=payload.model_dump(mode="json"),
        )
    except VerificationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    return VerificationRequiredResponse(verification_id=verification_id)


@router.post(
    "/institutions/confirm-create",
    response_model=InstitutionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=300, key_prefix="inst-confirm-create"))],
)
def confirm_create_institution(
    body: ConfirmCodeRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_platform_admin),
) -> InstitutionResponse:
    try:
        stored_payload = confirm_verification_code(
            db=db,
            verification_id=body.verification_id,
            code=body.code,
            expected_user_id=ctx.user_id,
            expected_purpose=VerificationPurpose.CREATE_INSTITUTION,
        )
    except VerificationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Re-validate uniqueness — time has passed since request-create, another
    # institution could have taken this code in the meantime.
    existing = db.query(Institution).filter(Institution.code == stored_payload["code"]).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Institution code '{stored_payload['code']}' is already taken",
        )

    institution = Institution(
        name=stored_payload["name"],
        code=stored_payload["code"],
        type=stored_payload["type"],
        country=stored_payload["country"],
        address=stored_payload.get("address"),
        official_email=stored_payload.get("official_email"),
        phone=stored_payload.get("phone"),
        website=stored_payload.get("website"),
    )
    db.add(institution)

    try:
        db.commit()
    except IntegrityError:
        # Defense in depth against a race condition between our check above
        # and this insert — the DB's own UNIQUE constraint is the real
        # guarantee, this just turns it into a clean HTTP response.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Institution code '{stored_payload['code']}' is already taken",
        )

    db.refresh(institution)
    return InstitutionResponse.model_validate(institution)


# ---------------------------------------------------------------------------
# Archive institution — soft delete via status field (step-up verified)
# ---------------------------------------------------------------------------


@router.post(
    "/institutions/{institution_id}/request-archive",
    response_model=VerificationRequiredResponse,
    dependencies=[Depends(rate_limit(max_requests=5, window_seconds=300, key_prefix="inst-request-archive"))],
)
def request_archive_institution(
    institution_id: str,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_platform_admin),
) -> VerificationRequiredResponse:
    institution = db.get(Institution, institution_id)
    if institution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")

    if institution.status == InstitutionStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Institution is already archived"
        )

    admin = db.get(User, ctx.user_id)

    verification_id = generate_verification_code(
        db=db,
        user_id=ctx.user_id,
        user_email=admin.email if admin else None,
        purpose=VerificationPurpose.DELETE_INSTITUTION,
        payload={"institution_id": str(institution.id), "institution_name": institution.name},
    )

    return VerificationRequiredResponse(verification_id=verification_id)


@router.post(
    "/institutions/confirm-archive",
    response_model=InstitutionResponse,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=300, key_prefix="inst-confirm-archive"))],
)
def confirm_archive_institution(
    body: ConfirmCodeRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_platform_admin),
) -> InstitutionResponse:
    try:
        stored_payload = confirm_verification_code(
            db=db,
            verification_id=body.verification_id,
            code=body.code,
            expected_user_id=ctx.user_id,
            expected_purpose=VerificationPurpose.DELETE_INSTITUTION,
        )
    except VerificationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    institution = db.get(Institution, stored_payload["institution_id"])
    if institution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")

    # This is the entire "delete" — nothing is removed from the database.
    # The tenant-isolation guard (get_current_context) already rejects any
    # request from a user whose institution.status != ACTIVE, so archiving
    # immediately locks out every user at this institution with no other
    # code changes needed.
    institution.status = InstitutionStatus.ARCHIVED
    institution.archived_at = datetime.now(timezone.utc)
    institution.archived_by = ctx.user_id

    db.commit()
    db.refresh(institution)

    return InstitutionResponse.model_validate(institution)


# ---------------------------------------------------------------------------
# List institutions
# ---------------------------------------------------------------------------


@router.get("/institutions", response_model=list[InstitutionResponse])
def list_institutions(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_platform_admin),
) -> list[InstitutionResponse]:
    query = db.query(Institution)
    if not include_archived:
        query = query.filter(Institution.status != InstitutionStatus.ARCHIVED)
    institutions = query.order_by(Institution.created_at.desc()).all()
    return [InstitutionResponse.model_validate(i) for i in institutions]



# ---------------------------------------------------------------------------
# Create Institution Admin for an existing institution
# ---------------------------------------------------------------------------


@router.post(
    "/institutions/{institution_id}/admins",
    response_model=InstitutionAdminCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=300, key_prefix="create-inst-admin"))],
)
def create_institution_admin(
    institution_id: str,
    payload: InstitutionAdminCreateRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_platform_admin),
) -> InstitutionAdminCreatedResponse:
    institution = db.get(Institution, institution_id)
    if institution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")

    if institution.status != InstitutionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot create an admin for an institution that is not active",
        )

    username = generate_username(
        db=db,
        first_name=payload.first_name,
        last_name=payload.last_name,
        institution_code=institution.code,
    )

    temporary_password = generate_temporary_password()

    from app.core.security import hash_password

    new_admin = User(
        institution_id=institution.id,
        username=username,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        password_hash=hash_password(temporary_password),
        role=UserRole.INSTITUTION_ADMIN,
        status=UserStatus.ACTIVE,
        must_change_password=True,
    )
    db.add(new_admin)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username already exists — please try again",
        )

    db.refresh(new_admin)

    return InstitutionAdminCreatedResponse(
        id=new_admin.id,
        username=new_admin.username,
        first_name=new_admin.first_name,
        last_name=new_admin.last_name,
        temporary_password=temporary_password,
        institution_id=institution.id,
    )

@router.get("/stats", response_model=PlatformStats)
def get_platform_stats(
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_platform_admin),
) -> PlatformStats:
    total_institutions = db.query(func.count(Institution.id)).scalar()
    active_institutions = (
        db.query(func.count(Institution.id))
        .filter(Institution.status == InstitutionStatus.ACTIVE)
        .scalar()
    )
    archived_institutions = (
        db.query(func.count(Institution.id))
        .filter(Institution.status == InstitutionStatus.ARCHIVED)
        .scalar()
    )
    total_users = db.query(func.count(User.id)).scalar()

    role_counts = db.query(User.role, func.count(User.id)).group_by(User.role).all()
    users_by_role = {role.value: count for role, count in role_counts}

    return PlatformStats(
        total_institutions=total_institutions,
        active_institutions=active_institutions,
        archived_institutions=archived_institutions,
        total_users=total_users,
        users_by_role=users_by_role,
    )