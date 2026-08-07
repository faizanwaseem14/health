"""
Calls Claude to turn a report's OCR word list into structured test
rows, using structured outputs (output_config.format) so the API
itself constrains the response to EXTRACTION_JSON_SCHEMA's shape.

That alone isn't trusted blindly: the response is still parsed and
validated against ExtractionResult ourselves. A response that hit
max_tokens can be syntactically valid JSON that's still incomplete, and
a schema is only as strict as the code that actually checks it.
Anything that doesn't come back clean raises ExtractionValidationError
- the caller decides what that means for the job, but this module never
hands back anything to save that hasn't passed both checks.
"""

import json
import logging

import anthropic
import pydantic

from app.ai.prompt import EXTRACTION_MODEL, SYSTEM_PROMPT
from app.ai.schema import EXTRACTION_JSON_SCHEMA, ExtractionResult
from app.config import settings

logger = logging.getLogger("medvault")

MAX_OUTPUT_TOKENS = 4096

# Built once at import - constructing the client makes no network call,
# same pattern as the R2 boto3 client and the Google Vision provider.
_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


class ExtractionError(Exception):
    """Base class for AI extraction errors."""


class ExtractionValidationError(ExtractionError):
    """
    Raised when Claude's response isn't valid JSON, doesn't match the
    strict schema, or was truncated. Never save what this was raised
    for - the caller should route the job to review instead.
    """


class ExtractionRefusedError(ExtractionError):
    """Raised when Claude declines to process the request (safety refusal)."""


def extract_structured_rows(word_list_text: str) -> ExtractionResult:
    response = _client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=SYSTEM_PROMPT,
        output_config={
            "format": {"type": "json_schema", "schema": EXTRACTION_JSON_SCHEMA}
        },
        messages=[{"role": "user", "content": word_list_text}],
    )

    if response.stop_reason == "refusal":
        raise ExtractionRefusedError("Claude declined to process this report's text.")
    if response.stop_reason == "max_tokens":
        raise ExtractionValidationError(
            "Claude's response was truncated (hit max_tokens) - "
            "output may be incomplete and cannot be trusted."
        )

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise ExtractionValidationError("Claude's response contained no text content.")

    try:
        raw = json.loads(text_blocks[0])
    except json.JSONDecodeError as error:
        raise ExtractionValidationError(
            f"Claude's response was not valid JSON: {error}"
        ) from error

    try:
        return ExtractionResult.model_validate(raw)
    except pydantic.ValidationError as error:
        raise ExtractionValidationError(
            f"Claude's response didn't match the extraction schema: {error}"
        ) from error
