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

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

# Importing app.config runs our environment-variable check immediately,
# before the server even starts. If a required key (Neon, Firebase, R2,
# ...) is missing from your .env file, the app refuses to start and tells
# you exactly what's missing, instead of crashing later with a confusing
# error deep inside some unrelated feature.
import app.config  # noqa: F401 (imported for this validation side-effect)
from app.auth.dependencies import get_current_user
from app.database import check_database_connection
from app.models import User

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


@app.get("/auth/me")
def read_current_user(user: User = Depends(get_current_user)):
    """
    A minimal PROTECTED route: requires a valid Firebase ID token in the
    "Authorization: Bearer <token>" header. Proves Task 9's login flow
    end to end - verify the token, then look up (or create) the matching
    MedVault user. A nicer response shape and richer error handling come
    in Tasks 15-16.
    """
    return {"id": str(user.id), "phone_number": user.phone_number}
