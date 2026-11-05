"""The visitor's IP address for rate limits and audit records.

Production traffic reaches the API through the Cloudflare Worker, so the
socket peer is a proxy address shared by every visitor. The worker sends the
real visitor address in CLIENT_IP_HEADER together with PROXY_SECRET_HEADER.
That header is used only when the secret matches, so a client calling the API
directly cannot choose the address it is rate limited under.
"""
import hmac
import ipaddress

from fastapi import Request

from app.core.config import settings

CLIENT_IP_HEADER = "x-skynet-client-ip"
PROXY_SECRET_HEADER = "x-skynet-proxy-secret"


def _valid_ip(value: str | None) -> str | None:
    try:
        return str(ipaddress.ip_address((value or "").strip()))
    except ValueError:
        return None


def client_ip(request: Request) -> str | None:
    secret = settings.PROXY_SHARED_SECRET
    supplied = request.headers.get(PROXY_SECRET_HEADER, "")
    if secret and supplied and hmac.compare_digest(supplied.encode(), secret.encode()):
        forwarded = _valid_ip(request.headers.get(CLIENT_IP_HEADER))
        if forwarded:
            return forwarded
    return _valid_ip(request.client.host if request.client else None)
