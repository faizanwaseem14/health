"""
Turns a verified Firebase token into a User row in our own database, and
provides `get_current_user` - a FastAPI dependency any protected route
can use to require a logged-in user.
"""

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.firebase import InvalidFirebaseTokenError, verify_id_token
from app.database import SessionLocal
from app.models import User

# auto_error=False means: if there's no Authorization header at all,
# FastAPI hands us `None` instead of raising its own generic error - so
# we can raise our own clear 401 message below.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_db():
    """
    Opens one database session for the lifetime of a single request, and
    always closes it afterward - even if the request raises an error.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def resolve_or_create_user(decoded_token: dict, db: Session) -> User:
    """
    Given an already-verified Firebase token, finds the matching User
    row - creating one the first time this person ever logs in.

    We match on `firebase_uid` (a stable ID Firebase assigns per person),
    not phone number or email, since `firebase_uid` is what Firebase
    itself treats as the permanent identity and it's present no matter
    which sign-in method (phone OTP, Google, ...) was used.
    """
    firebase_uid = decoded_token["uid"]
    phone_number = decoded_token.get("phone_number")
    email = decoded_token.get("email")

    if not phone_number and not email:
        # Every sign-in method this app supports attaches at least one
        # of these to the token - a token with neither isn't one we know
        # how to handle.
        raise InvalidFirebaseTokenError(
            "Firebase token has no phone_number or email - "
            "don't know how to identify this user."
        )

    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()

    if user is None:
        user = User(firebase_uid=firebase_uid, phone_number=phone_number, email=email)
        db.add(user)
    else:
        # Backfill whichever identifier this token has that the stored
        # row doesn't yet - e.g. someone who first signed in with Google
        # later links a phone number via Firebase account linking.
        if phone_number and not user.phone_number:
            user.phone_number = phone_number
        if email and not user.email:
            user.email = email

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    A FastAPI dependency: add `user: User = Depends(get_current_user)` to
    any route to require a logged-in user. Reads the
    "Authorization: Bearer <token>" header, verifies it with Firebase,
    and returns the matching User row - creating it on first login.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )

    try:
        decoded_token = verify_id_token(credentials.credentials)
        return resolve_or_create_user(decoded_token, db)
    except InvalidFirebaseTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired login token.",
        ) from error
