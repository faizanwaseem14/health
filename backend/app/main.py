"""
This is the entry point of the MedVault backend.

"Entry point" means: when you start the server, this is the file that runs
first and sets everything up.

Today (Day 1, Task 1) this file is intentionally tiny. It just proves the
server boots and responds to a request. Later tasks will add:
  - environment/config loading (Task 2)
  - a real /health route that checks the database (Task 14)
  - routers for auth, reports, etc. (later days)
"""

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Importing app.config runs our environment-variable check immediately,
# before the server even starts. If a required key (Neon, Firebase, R2,
# ...) is missing from your .env file, the app refuses to start and tells
# you exactly what's missing, instead of crashing later with a confusing
# error deep inside some unrelated feature.
import app.config  # noqa: F401 (imported for this validation side-effect)
from app.auth.dependencies import get_current_user, get_db
from app.auth.rate_limit import OtpRateLimitExceededError, check_and_record_otp_request
from app.auth.recovery import (
    RecoveryCodeInvalidError,
    generate_recovery_code,
    redeem_recovery_code,
)
from app.core.audit import record_audit_event
from app.database import check_database_connection
from app.models import User
from app.schemas.auth import OtpRequestPayload, RecoveryCodeRedeemPayload

logger = logging.getLogger("medvault")

# Create the FastAPI application object. Everything (routes, middleware,
# error handlers) gets attached to this single `app` object.
app = FastAPI(title="MedVault API")


@app.get("/")
def read_root():
    """
    A tiny placeholder route so you can confirm the server is running.

    Visiting http://127.0.0.1:8000/ in a browser should show this JSON.
    """
    return {"service": "MedVault API", "status": "running"}


@app.get("/health")
def health_check():
    """
    Public route (no login required) that proves the backend can actually
    reach the Neon database over an encrypted connection - not just that
    the web server process is running.
    """
    try:
        check_database_connection()
    except SQLAlchemyError:
        # Log the full error for us to debug, but never send database
        # internals (host, credentials, query text) back in the response.
        logger.exception("Database health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unreachable"},
        )

    return {"status": "ok", "database": "connected"}


@app.post("/auth/otp/request")
def request_otp(
    payload: OtpRequestPayload, request: Request, db: Session = Depends(get_db)
):
    """
    Called by the frontend BEFORE it asks Firebase to text a one-time
    code to this phone number. This does NOT send any SMS itself - that
    stays Firebase's job, on the frontend, on a later day. All this route
    does is check (and record) whether this phone number has requested
    too many codes recently, so we can say no before Firebase ever sends
    a text.
    """
    client_ip = request.client.host if request.client else None
    try:
        check_and_record_otp_request(payload.phone_number, db, ip_address=client_ip)
    except OtpRateLimitExceededError as error:
        return JSONResponse(
            status_code=429,
            content={"status": "error", "detail": str(error)},
        )

    return {"status": "ok"}


@app.get("/auth/me")
def read_current_user(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    A minimal PROTECTED route: requires a valid Firebase ID token in the
    "Authorization: Bearer <token>" header. Proves Task 9's login flow
    end to end - verify the token, then look up (or create) the matching
    MedVault user. A nicer response shape and richer error handling come
    in Tasks 15-16.
    """
    record_audit_event(
        db,
        action="view_own_profile",
        ip_address=request.client.host if request.client else "unknown",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        user_agent=request.headers.get("user-agent"),
    )
    return {"id": str(user.id), "phone_number": user.phone_number}


@app.post("/auth/recovery/generate")
def generate_recovery_code_route(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    PROTECTED route: an already-logged-in user asks for a backup
    recovery code. Returns the real code exactly once - after this
    response, only its hash is stored, so save it somewhere safe now.
    Generating a new code invalidates any earlier one.
    """
    code = generate_recovery_code(user, db)
    return {"recovery_code": code}


@app.post("/auth/recovery/redeem")
def redeem_recovery_code_route(
    payload: RecoveryCodeRedeemPayload, request: Request, db: Session = Depends(get_db)
):
    """
    PUBLIC route: lets someone who's lost access to their phone prove
    who they are with a saved recovery code instead. Every attempt is
    logged, whether it succeeds or fails.
    """
    client_ip = request.client.host if request.client else None
    try:
        user = redeem_recovery_code(
            payload.phone_number, payload.recovery_code, db, ip_address=client_ip
        )
    except RecoveryCodeInvalidError as error:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "detail": str(error)},
        )

    return {"id": str(user.id), "phone_number": user.phone_number}
