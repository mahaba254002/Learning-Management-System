"""
Teacher invitation flow.

Two distinct trust boundaries in this file, worth reading carefully:

1. Institution-scoped, authenticated routes (send/list/approve/reject) —
   protected by require_role(INSTITUTION_ADMIN), same tenant-isolation
   pattern as everywhere else.

2. PUBLIC, unauthenticated routes (view/submit) — accessed via the
   invite_token embedded in the link, with NO login required. The token
   itself is the only credential; this is the same trust model as a
   password-reset link.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, require_role
from app.core.invitation_token import generate_invite_token
from app.core.rate_limit import rate_limit
from app.core.security import hash_password
from app.db.session import get_db
from app.models.institution import Institution
from app.models.invitation import Invitation, InvitationRole, InvitationStatus
from app.models.teacher import EmploymentType, Gender, Teacher
from app.models.user import User, UserRole, UserStatus
from app.schemas.invitation import (
    InvitationApprovedResponse,
    InvitationPublicView,
    InvitationSummary,
    SendTeacherInvitationRequest,
    TeacherSubmissionRequest,
)
from app.services.password_service import generate_temporary_password
from app.services.username_service import generate_username


from app.core.config import settings
from app.services.email_failure_service import record_email_failure
from app.services.email_service import EmailSendError, send_email

INVITATION_VALIDITY_DAYS = 5

router = APIRouter(tags=["invitations"])


# ---------------------------------------------------------------------------
# Institution Admin: send, list, approve, reject
# ---------------------------------------------------------------------------



@router.post(
    "/api/institution/invitations/teachers",
    response_model=InvitationSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=3600, key_prefix="send-invite"))],
)
def send_teacher_invitation(
    payload: SendTeacherInvitationRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_role(UserRole.INSTITUTION_ADMIN)),
) -> InvitationSummary:
    invitation = Invitation(
        institution_id=ctx.institution_id,
        invited_role=InvitationRole.TEACHER,
        email=payload.email,
        invite_token=generate_invite_token(),
        status=InvitationStatus.SENT,
        invited_by=ctx.user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITATION_VALIDITY_DAYS),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    # In production this would be a real frontend URL, e.g.
    # https://yourapp.com/invite/{token}. Using FRONTEND_BASE_URL from
    # settings keeps this correct across dev/staging/production without
    # hardcoding a domain here.
    invite_link = f"{settings.FRONTEND_BASE_URL}/invite/{invitation.invite_token}"

    subject = "You've been invited to join as a teacher"
    html_body = (
        "<p>You have been invited to join as a teacher.</p>"
        f'<p><a href="{invite_link}">Click here to complete your profile</a></p>'
        f"<p>This invitation expires in {INVITATION_VALIDITY_DAYS} days.</p>"
    )

    try:
        send_email(to=payload.email, subject=subject, html_body=html_body)
    except EmailSendError as e:
        # Unlike verification codes, we do NOT roll back the invitation
        # here — the admin's intent (inviting this person) is still valid
        # and worth preserving even if the email didn't go out. We record
        # the failure and tell the admin plainly, so they can manually
        # share the link or retry later, rather than silently losing the
        # invitation entirely.
        record_email_failure(
            db=db,
            recipient=payload.email,
            subject=subject,
            email_type="TEACHER_INVITE",
            error_message=str(e),
            context={"invitation_id": str(invitation.id), "institution_id": str(ctx.institution_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The invitation was created, but the email could not be sent. "
                "Please try resending it, or share the link manually with the administrator."
            ),
        )

    return InvitationSummary.model_validate(invitation)

@router.get("/api/institution/invitations", response_model=list[InvitationSummary])
def list_invitations(
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_role(UserRole.INSTITUTION_ADMIN)),
) -> list[InvitationSummary]:
    invitations = (
        db.query(Invitation)
        .filter(Invitation.institution_id == ctx.institution_id)
        .order_by(Invitation.created_at.desc())
        .all()
    )
    return [InvitationSummary.model_validate(i) for i in invitations]


@router.post(
    "/api/institution/invitations/{invitation_id}/approve",
    response_model=InvitationApprovedResponse,
)
def approve_invitation(
    invitation_id: str,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_role(UserRole.INSTITUTION_ADMIN)),
) -> InvitationApprovedResponse:
    invitation = db.get(Invitation, invitation_id)

    # Tenant isolation check: this invitation must belong to the admin's
    # own institution — never trust the URL's invitation_id alone.
    if invitation is None or invitation.institution_id != ctx.institution_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if invitation.status != InvitationStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only submitted invitations can be approved",
        )

    data = invitation.submitted_data
    institution = db.get(Institution, ctx.institution_id)

    username = generate_username(
        db=db,
        first_name=data["first_name"],
        last_name=data["last_name"],
        institution_code=institution.code,
    )
    temporary_password = generate_temporary_password()

    new_user = User(
        institution_id=ctx.institution_id,
        username=username,
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=invitation.email,
        password_hash=hash_password(temporary_password),
        role=UserRole.TEACHER,
        status=UserStatus.ACTIVE,
        must_change_password=True,
    )
    try:
        db.add(new_user)
        db.flush()  # assigns new_user.id without committing yet, so we can reference it below

        new_teacher = Teacher(
            institution_id=ctx.institution_id,
            user_id=new_user.id,
            gender=Gender(data["gender"]),
            date_of_birth=date.fromisoformat(data["date_of_birth"]),
            phone=data.get("phone"),
            qualification=data["qualification"],
            specialization=data.get("specialization"),
            employment_type=EmploymentType(data["employment_type"]),
            invited_from=invitation.id,
        )
        db.add(new_teacher)

        invitation.status = InvitationStatus.APPROVED
        invitation.reviewed_by = ctx.user_id
        invitation.reviewed_at = datetime.now(timezone.utc)
        invitation.created_user_id = new_user.id

        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create the account — please try again",
        )

    db.refresh(new_user)

    # Email the credentials directly to the new teacher. If this fails, we
    # do NOT undo the account — it was already created successfully and is
    # a real, usable account. We record the failure so the admin can see
    # it, and the admin's on-screen copy (returned below regardless)
    # remains a valid fallback way to relay the credentials manually.
    subject = "Your Rollcall account is ready"
    html_body = (
        f"<p>Hello {new_user.first_name},</p>"
        "<p>Your account has been approved. Here are your login details:</p>"
        f"<p><strong>Username:</strong> {new_user.username}<br>"
        f"<strong>Temporary password:</strong> {temporary_password}</p>"
        "<p>You will be asked to set a new password the first time you log in.</p>"
        f'<p><a href="{settings.FRONTEND_BASE_URL}/login">Log in here</a></p>'
    )

    try:
        send_email(to=new_user.email, subject=subject, html_body=html_body)
        credentials_emailed = True
    except EmailSendError as e:
        record_email_failure(
            db=db,
            recipient=new_user.email,
            subject=subject,
            email_type="TEACHER_CREDENTIALS",
            error_message=str(e),
            context={"user_id": str(new_user.id), "institution_id": str(ctx.institution_id)},
        )
        credentials_emailed = False

    return InvitationApprovedResponse(
        id=new_user.id,
        username=new_user.username,
        temporary_password=temporary_password,
        credentials_emailed=credentials_emailed,
    )


@router.post("/api/institution/invitations/{invitation_id}/reject", response_model=InvitationSummary)
def reject_invitation(
    invitation_id: str,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_role(UserRole.INSTITUTION_ADMIN)),
) -> InvitationSummary:
    invitation = db.get(Invitation, invitation_id)

    if invitation is None or invitation.institution_id != ctx.institution_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if invitation.status not in (InvitationStatus.SENT, InvitationStatus.SUBMITTED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invitation cannot be rejected in its current state",
        )

    invitation.status = InvitationStatus.REJECTED
    invitation.reviewed_by = ctx.user_id
    invitation.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invitation)

    return InvitationSummary.model_validate(invitation)


# ---------------------------------------------------------------------------
# PUBLIC: viewed and submitted by the invited teacher, no login required
# ---------------------------------------------------------------------------


def _get_valid_invitation_or_404(db: Session, token: str) -> Invitation:
    invitation = db.query(Invitation).filter(Invitation.invite_token == token).first()
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if invitation.status == InvitationStatus.SENT and datetime.now(timezone.utc) > invitation.expires_at:
        invitation.status = InvitationStatus.EXPIRED
        db.commit()

    return invitation


@router.get("/api/invitations/{token}", response_model=InvitationPublicView)
def view_invitation(
    token: str,
    db: Session = Depends(get_db),
) -> InvitationPublicView:
    invitation = _get_valid_invitation_or_404(db, token)
    institution = db.get(Institution, invitation.institution_id)

    return InvitationPublicView(
        institution_name=institution.name,
        invited_role=invitation.invited_role.value,
        email=invitation.email,
        status=invitation.status,
        expires_at=invitation.expires_at,
    )


@router.post(
    "/api/invitations/{token}/submit",
    response_model=InvitationPublicView,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=3600, key_prefix="submit-invite"))],
)
def submit_invitation(
    token: str,
    payload: TeacherSubmissionRequest,
    db: Session = Depends(get_db),
) -> InvitationPublicView:
    invitation = _get_valid_invitation_or_404(db, token)

    if invitation.status != InvitationStatus.SENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invitation has already been submitted, is expired, or is no longer valid",
        )

    # Validate enum-like fields early with a clear error, rather than
    # letting a bad value surface confusingly later at approval time.
    try:
        Gender(payload.gender)
        EmploymentType(payload.employment_type)
        date.fromisoformat(payload.date_of_birth)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid field value: {e}")

    invitation.submitted_data = payload.model_dump()
    invitation.status = InvitationStatus.SUBMITTED
    db.commit()
    db.refresh(invitation)

    institution = db.get(Institution, invitation.institution_id)

    return InvitationPublicView(
        institution_name=institution.name,
        invited_role=invitation.invited_role.value,
        email=invitation.email,
        status=invitation.status,
        expires_at=invitation.expires_at,
    )