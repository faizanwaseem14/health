"""Request/response shapes for profile-related routes."""

from datetime import date

from pydantic import BaseModel, Field


class ProfileCreatePayload(BaseModel):
    """The body the frontend sends to set up a profile for the logged-in user."""

    full_name: str = Field(..., min_length=1)
    date_of_birth: date | None = None
    sex: str | None = None
