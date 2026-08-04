"""
Global error handling: turns exceptions raised ANYWHERE in the app into
clear, structured JSON - and makes sure nothing internal (a stack trace,
a database error, a connection string) ever reaches the client.

This is registered once, in main.py, and applies to every route
automatically. Routes don't need their own try/except for these cases -
that IS the point: one place decides how errors look, instead of each
route deciding it slightly differently (which is how we were doing it
before this task).
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.rate_limit import OtpRateLimitExceededError
from app.auth.recovery import RecoveryCodeInvalidError

logger = logging.getLogger("medvault")


def _error_response(status_code: int, detail) -> JSONResponse:
    """Every error response - no matter where it came from - has this same shape."""
    return JSONResponse(
        status_code=status_code, content={"status": "error", "detail": detail}
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Call this once, right after creating the FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        # Turn Pydantic's error list into short, readable strings, e.g.
        # "body.phone_number: field required" - useful to whoever is
        # calling the API, without dumping raw Python internals.
        problems = [
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        ]
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, problems)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        # Covers every HTTPException raised anywhere - 401s from
        # get_current_user, 404s from the ownership guard, even
        # FastAPI's own 404 for a route that doesn't exist - same shape,
        # every time.
        return _error_response(exc.status_code, exc.detail)

    @app.exception_handler(OtpRateLimitExceededError)
    async def handle_otp_rate_limit(request: Request, exc: OtpRateLimitExceededError):
        return _error_response(status.HTTP_429_TOO_MANY_REQUESTS, str(exc))

    @app.exception_handler(RecoveryCodeInvalidError)
    async def handle_recovery_code_invalid(
        request: Request, exc: RecoveryCodeInvalidError
    ):
        return _error_response(status.HTTP_401_UNAUTHORIZED, str(exc))

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError):
        # Log the full error for us to debug, but NEVER send database
        # internals (host, credentials, query text) back in the response.
        logger.exception("Unhandled database error")
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "A database error occurred. Please try again.",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        # The final safety net: whatever this is, the client NEVER sees
        # its message or a stack trace - only a generic message. Full
        # details go to our own logs, never to the response.
        logger.exception("Unhandled exception")
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "An unexpected error occurred. Please try again.",
        )
