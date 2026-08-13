"""
Central place that loads configuration from environment variables.

Why this file exists:
  - We NEVER put real secrets (passwords, API keys) directly in code.
  - Instead, secrets live in a `.env` file (gitignored, so it's never
    uploaded to GitHub) and this file reads them into Python.
  - If something REQUIRED is missing, the app refuses to start and tells
    you exactly what's missing — instead of failing later with a
    confusing error buried inside some unrelated feature.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load variables from a .env file (if one exists) into the environment.
# This only matters for local development — in production, the hosting
# platform usually sets real environment variables directly.
load_dotenv()

# Every environment variable the app will EVER need, across Day 1 and
# Day 2 features.
#   required=True  -> the app cannot run at all without this value.
#   required=False -> fine to leave blank for now (wired up on a later day).
_ENV_SPEC = [
    # --- Database (Neon Postgres) ---
    ("DATABASE_URL", True),
    # --- Firebase Auth (phone OTP verification) ---
    ("FIREBASE_SERVICE_ACCOUNT_JSON", True),
    # --- Cloudflare R2 (private file storage) ---
    ("R2_ACCOUNT_ID", True),
    ("R2_ACCESS_KEY_ID", True),
    ("R2_SECRET_ACCESS_KEY", True),
    ("R2_BUCKET_NAME", True),
    ("R2_ENDPOINT_URL", True),
    # --- Redis (Upstash), REST API — powers the background job queue ---
    ("UPSTASH_REDIS_REST_URL", True),
    ("UPSTASH_REDIS_REST_TOKEN", True),
    # --- OCR: Google Cloud Vision — only needed if OCR_PROVIDER=google_vision ---
    ("GOOGLE_VISION_API_KEY", False),
    # --- AI extraction (Claude / Anthropic) — every processed report uses this ---
    ("ANTHROPIC_API_KEY", True),
]

# OCR_PROVIDER isn't a simple "present or blank" secret like the ones
# above — it's a small closed set of valid values with a safe default,
# so it gets its own validation below instead of living in _ENV_SPEC.
_ALLOWED_OCR_PROVIDERS = {"tesseract", "google_vision"}
_DEFAULT_OCR_PROVIDER = "tesseract"

# TRUST_CONFIDENCE_THRESHOLD (app/trust/) is the same kind of "has a
# safe default, tune later" setting as OCR_PROVIDER — not a secret, so
# it doesn't belong in _ENV_SPEC either. Below this, a result's AI
# confidence isn't enough to trust it on its own.
_DEFAULT_TRUST_CONFIDENCE_THRESHOLD = 0.8


@dataclass(frozen=True)
class Settings:
    """A typed, read-only bundle of every config value the app uses."""

    database_url: str
    firebase_service_account_json: str
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str
    r2_endpoint_url: str
    upstash_redis_rest_url: str
    upstash_redis_rest_token: str
    ocr_provider: str
    google_vision_api_key: str | None
    anthropic_api_key: str
    trust_confidence_threshold: float


def load_settings() -> Settings:
    """
    Read every variable listed in _ENV_SPEC from the environment.

    If ANY required variable is missing, we collect ALL of the missing
    names and raise ONE clear error listing every single one — so you can
    fix your .env file in one pass instead of restarting the server
    over and over to discover missing keys one at a time.
    """
    values: dict[str, str | None] = {}
    missing: list[str] = []

    for name, required in _ENV_SPEC:
        value = os.environ.get(name) or None
        if required and not value:
            missing.append(name)
        values[name] = value

    if missing:
        missing_list = "\n".join(f"  - {name}" for name in missing)
        raise RuntimeError(
            "\n\n"
            "MedVault cannot start: required environment variables are missing.\n\n"
            f"Missing:\n{missing_list}\n\n"
            "Fix: copy backend/.env.example to backend/.env (if you haven't "
            "already) and fill in real values. See SETUP.md for where to get "
            "each one.\n"
        )

    ocr_provider = os.environ.get("OCR_PROVIDER", "").strip() or _DEFAULT_OCR_PROVIDER
    if ocr_provider not in _ALLOWED_OCR_PROVIDERS:
        raise RuntimeError(
            "\n\n"
            f"MedVault cannot start: OCR_PROVIDER={ocr_provider!r} is not valid.\n\n"
            f"Must be one of: {sorted(_ALLOWED_OCR_PROVIDERS)}.\n"
        )
    if ocr_provider == "google_vision" and not values["GOOGLE_VISION_API_KEY"]:
        raise RuntimeError(
            "\n\n"
            "MedVault cannot start: OCR_PROVIDER=google_vision but "
            "GOOGLE_VISION_API_KEY is blank.\n\n"
            "Fix: add a real key to backend/.env (see SETUP.md), or set "
            "OCR_PROVIDER=tesseract to use the free local OCR provider "
            "instead.\n"
        )

    trust_threshold_raw = os.environ.get(
        "TRUST_CONFIDENCE_THRESHOLD", ""
    ).strip() or str(_DEFAULT_TRUST_CONFIDENCE_THRESHOLD)
    try:
        trust_confidence_threshold = float(trust_threshold_raw)
    except ValueError:
        raise RuntimeError(
            "\n\n"
            "MedVault cannot start: TRUST_CONFIDENCE_THRESHOLD="
            f"{trust_threshold_raw!r} is not a valid number.\n\n"
            "Fix: set it to a decimal between 0.0 and 1.0 in backend/.env (e.g. 0.8), "
            "or leave it unset to use the default.\n"
        )
    if not 0.0 <= trust_confidence_threshold <= 1.0:
        raise RuntimeError(
            "\n\n"
            "MedVault cannot start: TRUST_CONFIDENCE_THRESHOLD="
            f"{trust_confidence_threshold!r} is out of range.\n\n"
            "Must be between 0.0 and 1.0 (inclusive).\n"
        )

    return Settings(
        database_url=values["DATABASE_URL"],
        firebase_service_account_json=values["FIREBASE_SERVICE_ACCOUNT_JSON"],
        r2_account_id=values["R2_ACCOUNT_ID"],
        r2_access_key_id=values["R2_ACCESS_KEY_ID"],
        r2_secret_access_key=values["R2_SECRET_ACCESS_KEY"],
        r2_bucket_name=values["R2_BUCKET_NAME"],
        r2_endpoint_url=values["R2_ENDPOINT_URL"],
        upstash_redis_rest_url=values["UPSTASH_REDIS_REST_URL"],
        upstash_redis_rest_token=values["UPSTASH_REDIS_REST_TOKEN"],
        ocr_provider=ocr_provider,
        google_vision_api_key=values["GOOGLE_VISION_API_KEY"],
        anthropic_api_key=values["ANTHROPIC_API_KEY"],
        trust_confidence_threshold=trust_confidence_threshold,
    )


# Loaded once, the first time any file does `from app.config import settings`.
# Every other file reuses this same validated object instead of re-reading
# environment variables themselves.
settings = load_settings()

print("[config] All required environment variables are present.")
