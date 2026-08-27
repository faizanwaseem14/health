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
from app.config import settings
from app.core.errors import register_exception_handlers
from app.routers import auth, health, ocr, profiles, reports, results, shares

# Create the FastAPI application object. Everything (routes, middleware,
# error handlers) gets attached to this single `app` object.
app = FastAPI(title="MedVault API")

# The frontend runs on a different origin than this API, so the browser
# blocks its requests unless we explicitly allow them here.
#
# Two allow-lists, both active at once (a request only needs to match
# ONE of them):
#   - allow_origin_regex: ANY localhost/127.0.0.1 port. Vite picks a
#     port on its own (5173, or the next free one if that's taken), so
#     rather than list one exact port this matches all of them. Safe to
#     leave on permanently, even in production: a browser only sends an
#     Origin header of "http://localhost:<port>" when the page actually
#     was loaded from localhost on that same machine - a real
#     attacker's site can't forge that - so this can never be satisfied
#     by anything other than someone's own local dev server, no matter
#     where this backend itself is deployed.
#   - allow_origins: the deployed frontend's real origin(s), from
#     CORS_ALLOWED_ORIGINS (see app/config.py) - empty by default, so a
#     fresh deployment fails closed (the browser blocks everything from
#     a real origin) rather than failing open, until that's set.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1):\d+$",
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
# reports.router holds report upload/status/retry (protected, ownership-checked).
# results.router holds extracted results, on-demand explanations, and
# corrections (protected, ownership-checked).
# ocr.router holds OCR evidence + page-image inspection (protected,
# ownership-checked).
# shares.router holds share-link management (protected, ownership-
# checked) AND the public, no-login doctor view at GET /public/shares/
# {token} - see app/routers/shares.py for why one router holds both.
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(reports.router)
app.include_router(results.router)
app.include_router(ocr.router)
app.include_router(shares.router)
