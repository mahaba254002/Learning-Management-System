"""Safaricom Daraja client: STK push, STK query and paybill URL registration."""
import base64
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings

logger = logging.getLogger("app.mpesa")
HOSTS = {"sandbox": "https://sandbox.safaricom.co.ke", "production": "https://api.safaricom.co.ke"}
_token = {"value": "", "expires": 0.0}
_token_lock = threading.Lock()


class MpesaError(Exception):
    pass


def configured():
    return all((settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET, settings.MPESA_SHORTCODE,
                settings.MPESA_PASSKEY, settings.MPESA_CALLBACK_BASE_URL, settings.MPESA_CALLBACK_SECRET))


def is_till():
    return bool(settings.MPESA_TILL_NUMBER)


def pay_to_number():
    return settings.MPESA_TILL_NUMBER or settings.MPESA_SHORTCODE


def normalise_phone(value):
    """07XXXXXXXX, 01XXXXXXXX, +2547... or 2547... become 2547XXXXXXXX."""
    digits = re.sub(r"[\s-]", "", value or "").removeprefix("+")
    if re.fullmatch(r"0[17]\d{8}", digits):
        digits = "254" + digits[1:]
    if not re.fullmatch(r"254[17]\d{8}", digits):
        raise ValueError("Enter a Safaricom number such as 0712 345 678")
    return digits


def callback_url(name):
    return f"{settings.MPESA_CALLBACK_BASE_URL.rstrip('/')}/api/payments/mpesa/{settings.MPESA_CALLBACK_SECRET}/{name}"


def _request(path, body=None, token=None, basic=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if basic:
        headers["Authorization"] = f"Basic {basic}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(HOSTS[settings.MPESA_ENVIRONMENT] + path, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"{}")
        except ValueError:
            detail = {}
        # A pending STK query answers with an HTTP error; callers read the body.
        if detail:
            return detail
        logger.error("Daraja %s failed: HTTP %s", path, exc.code)
        raise MpesaError("M-Pesa did not accept the request. Try again shortly.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.error("Daraja %s unreachable: %s", path, exc)
        raise MpesaError("M-Pesa could not be reached. Try again shortly.") from exc


def access_token():
    with _token_lock:
        if _token["value"] and _token["expires"] > time.time() + 60:
            return _token["value"]
        basic = base64.b64encode(f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}".encode()).decode()
        data = _request("/oauth/v1/generate?grant_type=client_credentials", basic=basic)
        if not data.get("access_token"):
            raise MpesaError("M-Pesa sign-in failed. Check the Daraja keys.")
        _token.update(value=data["access_token"], expires=time.time() + int(data.get("expires_in", 3599)))
        return _token["value"]


def _password():
    stamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")
    raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{stamp}"
    return base64.b64encode(raw.encode()).decode(), stamp


def stk_push(*, phone, amount, account_reference, description):
    password, stamp = _password()
    body = dict(BusinessShortCode=settings.MPESA_SHORTCODE, Password=password, Timestamp=stamp,
                TransactionType="CustomerBuyGoodsOnline" if is_till() else "CustomerPayBillOnline",
                Amount=int(amount), PartyA=phone, PartyB=pay_to_number(), PhoneNumber=phone,
                CallBackURL=callback_url("stk-callback"), AccountReference=account_reference[:12], TransactionDesc=description[:13])
    return _request("/mpesa/stkpush/v1/processrequest", body, token=access_token())


def stk_query(checkout_request_id):
    password, stamp = _password()
    body = dict(BusinessShortCode=settings.MPESA_SHORTCODE, Password=password, Timestamp=stamp, CheckoutRequestID=checkout_request_id)
    return _request("/mpesa/stkpushquery/v1/query", body, token=access_token())


def register_paybill_urls():
    body = dict(ShortCode=pay_to_number(), ResponseType="Completed",
                ConfirmationURL=callback_url("c2b-confirmation"), ValidationURL=callback_url("c2b-validation"))
    return _request("/mpesa/c2b/v1/registerurl", body, token=access_token())
