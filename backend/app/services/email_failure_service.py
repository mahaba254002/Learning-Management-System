from sqlalchemy.orm import Session

from app.models.email_failure import EmailFailure


def record_email_failure(
    *, db: Session, recipient: str, subject: str, email_type: str, error_message: str, context: dict | None = None
) -> None:
    failure = EmailFailure(
        recipient=recipient,
        subject=subject,
        email_type=email_type,
        error_message=error_message,
        context=context,
    )
    db.add(failure)
    db.commit()