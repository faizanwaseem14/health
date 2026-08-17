"""
Verifies Firebase phone-login tokens on the backend.

IMPORTANT - how phone login actually works here: this backend never sends
an SMS or talks to a phone number directly. The FRONTEND (on a later day)
uses Firebase's own SDK to send the OTP text message and let the user
type it in. Once Firebase confirms the code was right, the frontend gets
back a short-lived "ID token" (a signed JWT) and sends THAT to us. All we
do here is check that the token is genuinely signed by Firebase for OUR
project and hasn't expired - then read the phone number out of it. We
never generate, store, or see the actual 6-digit OTP code.
"""

import json

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from firebase_admin.exceptions import FirebaseError

from app.config import settings

_firebase_app: firebase_admin.App | None = None  # built lazily, see below


class InvalidFirebaseTokenError(Exception):
    """Raised when a token isn't a valid, current Firebase ID token."""


def _get_firebase_app() -> firebase_admin.App:
    """
    Creates (once) and reuses the Firebase Admin SDK app object.

    This is deliberately lazy - it does NOT run when this file is
    imported, only the first time something actually tries to verify a
    token. That way, importing the app doesn't blow up just because
    the Firebase credential in your .env isn't a real one yet; you'll
    only see an error from the thing that actually needed it.

    Two ways to supply the credential (see backend/.env.example):
      - FIREBASE_SERVICE_ACCOUNT_FILE: a path to the .json file
        downloaded from Firebase console. Preferred - the Admin SDK
        reads and parses the file itself, so there's no copy/paste
        formatting to get wrong.
      - FIREBASE_SERVICE_ACCOUNT_JSON: that same file's entire
        contents, pasted as one line.
    """
    global _firebase_app
    if _firebase_app is None:
        if settings.firebase_service_account_file:
            file_path = settings.firebase_service_account_file
            try:
                cred = credentials.Certificate(file_path)
            except IOError as error:
                raise RuntimeError(
                    "Couldn't read the Firebase service account file at "
                    f"FIREBASE_SERVICE_ACCOUNT_FILE={file_path!r}. Check the path "
                    "is correct (relative paths are resolved from wherever you "
                    "started uvicorn, usually backend/)."
                ) from error
        else:
            json_value = settings.firebase_service_account_json
            try:
                service_account_info = json.loads(json_value)
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    "FIREBASE_SERVICE_ACCOUNT_JSON in your .env isn't valid JSON "
                    "(still the placeholder, or the private_key's newlines broke "
                    "when pasting). Easier fix: download the service account file "
                    "from Firebase console and point FIREBASE_SERVICE_ACCOUNT_FILE "
                    "at it instead - see backend/.env.example."
                ) from error
            cred = credentials.Certificate(service_account_info)
        _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def verify_id_token(id_token: str) -> dict:
    """
    Verifies a Firebase ID token sent by the frontend and returns its
    decoded contents - a dict that includes at least "uid" and, for
    phone sign-in, "phone_number".

    Raises InvalidFirebaseTokenError if the token is missing, expired,
    malformed, or wasn't issued by our own Firebase project. We always
    convert Firebase's own errors into this one clear type, rather than
    letting them leak into the rest of the app.
    """
    app = _get_firebase_app()
    try:
        return firebase_auth.verify_id_token(id_token, app=app)
    except (ValueError, FirebaseError) as error:
        raise InvalidFirebaseTokenError(str(error)) from error
