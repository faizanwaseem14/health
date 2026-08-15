"""
Profile routes: a profile is who one person's health records live
under - the account holder themselves, or a dependent they manage. A
user can end up with more than one profile (a whole family), but needs
at least one before they can upload anything.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.core.responses import success_response
from app.models import Profile, User
from app.schemas.profile import ProfileCreatePayload

router = APIRouter()


def _serialize(profile: Profile) -> dict:
    return {
        "id": str(profile.id),
        "full_name": profile.full_name,
        "date_of_birth": (
            profile.date_of_birth.isoformat() if profile.date_of_birth else None
        ),
        "relationship_to_owner": profile.relationship_to_owner,
        "sex": profile.sex,
        "blood_type": profile.blood_type,
    }


@router.get("/profiles")
def list_my_profiles(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    PROTECTED route: every profile the logged-in user owns - the
    frontend uses this to tell a first-time user (an empty list, who
    still needs profile setup) from a returning one (who can skip
    straight past that screen).
    """
    profiles = (
        db.query(Profile)
        .filter(Profile.user_id == user.id)
        .order_by(Profile.created_at)
        .all()
    )
    return success_response([_serialize(profile) for profile in profiles])


@router.post("/profiles", status_code=201)
def create_profile(
    payload: ProfileCreatePayload,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: creates a new profile owned by the logged-in user.
    The very first profile anyone creates is themselves - it keeps the
    model's "self" default rather than setting relationship_to_owner
    here. Adding a profile for a dependent (a child, a parent) is a
    separate, dedicated flow on a later day, not this one.
    """
    profile = Profile(
        user_id=user.id,
        full_name=payload.full_name,
        date_of_birth=payload.date_of_birth,
        sex=payload.sex,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return success_response(_serialize(profile), status_code=201)
