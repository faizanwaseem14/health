"""
This is the entry point of the MedVault backend.

"Entry point" means: when you start the server, this is the file that
runs first and sets everything up. It's deliberately small - it just
builds the FastAPI app and plugs in the routers. The actual routes live
in app/routers/ (grouped by feature: health, auth, ...), and everything
else (config, database, auth, storage) lives in its own module under
app/ - main.py doesn't know the details of any of it.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importing app.config runs our environment-variable check immediately,
# before the server even starts. If a required key (Neon, Firebase, R2,
# ...) is missing from your .env file, the app refuses to start and tells
# you exactly what's missing, instead of crashing later with a confusing
# error deep inside some unrelated feature.
import app.config  # noqa: F401 (imported for this validation side-effect)
from app.core.errors import register_exception_handlers
from app.routers import auth, health, profiles, reports

# Create the FastAPI application object. Everything (routes, middleware,
# error handlers) gets attached to this single `app` object.
app = FastAPI(title="MedVault API")

# The frontend (Vite dev server) runs on a different origin than this
# API, so the browser blocks its requests unless we explicitly allow
# them here - this is what makes "run the frontend and backend
# together locally" actually work. Both localhost and 127.0.0.1 are
# listed since browsers treat them as different origins even though
# they're the same machine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registers the global error handlers (Task 15) - every route below
# automatically gets clear, structured errors with no internals leaked,
# without needing its own try/except for these cases.
register_exception_handlers(app)

# health.router holds "/" and "/health" (both public).
# auth.router holds everything under "/auth/..." (a mix of public and
# identity-checked routes - see app/routers/auth.py for which is which).
# profiles.router holds profile setup/listing (protected).
# reports.router holds report upload (protected, ownership-checked).
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(reports.router)
