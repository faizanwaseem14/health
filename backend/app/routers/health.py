"""
Public, unauthenticated routes: just enough to prove the server (and its
database connection) is alive. Nothing here needs a login.
"""

from fastapi import APIRouter

from app.core.responses import success_response
from app.database import check_database_connection

router = APIRouter()


@router.get("/")
def read_root():
    """
    A tiny placeholder route so you can confirm the server is running.

    Visiting http://127.0.0.1:8000/ in a browser should show this JSON.
    """
    return success_response({"service": "MedVault API", "status": "running"})


@router.get("/health")
def health_check():
    """
    Public route (no login required) that proves the backend can actually
    reach the Neon database over an encrypted connection - not just that
    the web server process is running.

    If the database is unreachable, check_database_connection() raises a
    SQLAlchemyError. We don't catch it here - the global error handler
    (Task 15, app/core/errors.py) turns it into a clean 503 without ever
    exposing connection details, and this route stays simple.
    """
    check_database_connection()
    return success_response({"database": "connected"})
