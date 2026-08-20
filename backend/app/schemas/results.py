"""Request/response shapes for result-correction routes."""

from pydantic import BaseModel, Field

# Only "value" is correctable for now - the one field the results
# screen actually lets someone fix. Deliberately a closed set (not
# "any column name") so this endpoint can never be used to edit
# something like trust_status or id.
CORRECTABLE_FIELDS = {"value"}


class CorrectionCreatePayload(BaseModel):
    """The body the frontend sends to correct one field on a result."""

    field_name: str = Field(..., min_length=1)
    new_value: str = Field(..., min_length=1)
    reason: str | None = None
