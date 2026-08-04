"""Request/response shapes for auth-related routes."""

from pydantic import BaseModel, Field


class OtpRequestPayload(BaseModel):
    """The body the frontend sends before it asks Firebase to text an OTP."""

    phone_number: str = Field(..., min_length=1)
