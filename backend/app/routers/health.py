"""
Public, unauthenticated routes: just enough to prove the server (and its
database connection) is alive. Nothing here needs a login.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.database import check_database_connection

logger = logging.getLogger("medvault")

router = APIRouter()


@router.get("/")
def read_root():
    """
    A tiny placeholder route so you can confirm the server is running.

    Visiting http://127.0.0.1:8000/ in a browser should show this JSON.
    """
    return {"service": "MedVault API", "status": "running"}


@router.get("/health")
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
