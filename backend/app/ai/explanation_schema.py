"""
The strict explanation schema: exactly what a plain-language test
explanation must contain. Claude's raw response is validated against
this - anything that doesn't fit (missing field, wrong type, extra
field) is rejected by Pydantic before it ever reaches the database.
Same two-layer pattern as app/ai/schema.py: EXPLANATION_JSON_SCHEMA
constrains Claude's structured-outputs response, and
ExplanationResult.model_validate() is the second, independent check.

This schema only shapes the RESPONSE - it says nothing about what the
explanation is allowed to say. That's enforced separately in
app/ai/explanation.py's advice-language guard.
"""

from pydantic import BaseModel, ConfigDict, Field


class ExplanationResult(BaseModel):
    """A plain-language description of what one test measures."""

    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(..., min_length=1)


EXPLANATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
    },
    "required": ["explanation"],
    "additionalProperties": False,
}
