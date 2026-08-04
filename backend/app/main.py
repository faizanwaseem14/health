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

# Importing app.config runs our environment-variable check immediately,
# before the server even starts. If a required key (Neon, Firebase, R2,
# ...) is missing from your .env file, the app refuses to start and tells
# you exactly what's missing, instead of crashing later with a confusing
# error deep inside some unrelated feature.
import app.config  # noqa: F401 (imported for this validation side-effect)
from app.routers import auth, health

# Create the FastAPI application object. Everything (routes, middleware,
# error handlers) gets attached to this single `app` object.
app = FastAPI(title="MedVault API")

# health.router holds "/" and "/health" (both public).
# auth.router holds everything under "/auth/..." (a mix of public and
# identity-checked routes - see app/routers/auth.py for which is which).
app.include_router(health.router)
app.include_router(auth.router)
