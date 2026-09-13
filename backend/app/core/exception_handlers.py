"""
Global exception handling.

Concept note: FastAPI lets you register a handler for any exception type
that catches it application-wide, instead of every route needing its own
try/except. We register one for the generic `Exception` base class — this
is the catch-all for anything we didn't explicitly anticipate (a bug, a
database hiccup, etc.). Expected errors (like "institution not found")
should still be raised as HTTPException with a proper status code and
message, as we've been doing — this handler is specifically the safety net
for the *unexpected* ones.
"""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("app.errors")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # A short random ID lets you correlate "the user reported an error"
        # with the exact log line, without exposing internal details to them.
        error_id = str(uuid.uuid4())[:8]

        logger.exception(f"Unhandled exception [error_id={error_id}] on {request.method} {request.url.path}")

        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected error occurred. Please try again or contact support.",
                "error_id": error_id,
            },
        )