"""
The strict extraction schema: exactly what one extracted test row must
contain. Claude's raw response is validated against this - anything
that doesn't fit (missing field, wrong type, extra field) is rejected
by Pydantic before it ever reaches the database.

EXTRACTION_JSON_SCHEMA is the same shape expressed as JSON Schema, sent
to Claude's structured-outputs feature so the API itself constrains the
response - ExtractionResult.model_validate() is the second, independent
check on top of that (a truncated response can still be syntactically
valid JSON that doesn't fully match).
"""

from pydantic import BaseModel, ConfigDict, Field


class ExtractedTestRow(BaseModel):
    """One test result, read straight off the report - never computed or guessed."""

    model_config = ConfigDict(extra="forbid")

    raw_test_name: str = Field(..., min_length=1)
    canonical_test_name: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    unit: str | None = None
    # Exactly as printed on the report - never hardcoded or looked up.
    reference_range: str | None = None
    date: str | None = None
    lab: str | None = None
    # Indices into the numbered OCR word list this row was extracted
    # from - what lets every value trace back to its exact source text
    # and position.
    evidence_word_indices: list[int] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[ExtractedTestRow] = Field(default_factory=list)


EXTRACTION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "raw_test_name": {"type": "string"},
                    "canonical_test_name": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": ["string", "null"]},
                    "reference_range": {"type": ["string", "null"]},
                    "date": {"type": ["string", "null"]},
                    "lab": {"type": ["string", "null"]},
                    "evidence_word_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "confidence": {"type": "number"},
                },
                "required": [
                    "raw_test_name",
                    "canonical_test_name",
                    "value",
                    "unit",
                    "reference_range",
                    "date",
                    "lab",
                    "evidence_word_indices",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["rows"],
    "additionalProperties": False,
}
