from html import escape

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.schemas.contact import ProductEnquiryRequest
from app.services.email_service import EmailSendError, send_email

router = APIRouter(prefix="/api/contact", tags=["contact"])


@router.post("/enquiries", dependencies=[Depends(rate_limit(max_requests=3, window_seconds=600, key_prefix="product-enquiry"))])
def send_product_enquiry(payload: ProductEnquiryRequest) -> dict[str, str]:
    if not settings.PRODUCT_ENQUIRY_EMAIL:
        raise HTTPException(status_code=503, detail="Product enquiries are temporarily unavailable.")

    # Recipients and subject are server controlled. All visitor text is escaped.
    fields = [("Name", payload.name), ("Email", payload.email),
              ("Institution", payload.institution), ("Category", payload.sector.value)]
    body = "<h1>Skynet product enquiry</h1>" + "".join(
        f"<p><strong>{label}:</strong> {escape(value)}</p>" for label, value in fields
    ) + f'<p style="white-space: pre-wrap">{escape(payload.message)}</p>'
    try:
        send_email(to=settings.PRODUCT_ENQUIRY_EMAIL, subject=f"Skynet enquiry: {payload.sector.value}", html_body=body)
    except EmailSendError as exc:
        raise HTTPException(status_code=503, detail="Your enquiry could not be sent. Please try again later.") from exc
    return {"message": "Your enquiry has been sent."}
