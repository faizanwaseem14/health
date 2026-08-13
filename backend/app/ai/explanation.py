"""
Calls Claude to generate a plain-language description of what a lab
test measures, using structured outputs (output_config.format) so the
API itself constrains the response to EXPLANATION_JSON_SCHEMA's shape -
same pattern as app/ai/extraction.py.

That alone isn't trusted blindly, and neither is the prompt wording in
app/ai/explanation_prompt.py: every response is also checked for
advice/diagnosis/recommendation language (contains_advice_language)
before it's ever handed back to the caller. Anything that fails any
check raises ExplanationValidationError - this module never hands back
anything to save that hasn't passed every check.
"""

import json
import logging
import re

import anthropic
import pydantic

from app.ai.explanation_prompt import EXPLANATION_MODEL, SYSTEM_PROMPT
from app.ai.explanation_schema import EXPLANATION_JSON_SCHEMA, ExplanationResult
from app.config import settings

logger = logging.getLogger("medvault")

MAX_OUTPUT_TOKENS = 512

# Built once at import - constructing the client makes no network call,
# same pattern as app/ai/extraction.py's client.
_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


class ExplanationError(Exception):
    """Base class for AI explanation errors."""


class ExplanationValidationError(ExplanationError):
    """
    Raised when Claude's response isn't valid JSON, doesn't match the
    strict schema, was truncated, or contains advice/diagnosis/
    recommendation language. Never save what this was raised for.
    """


class ExplanationRefusedError(ExplanationError):
    """Raised when Claude declines to process the request (safety refusal)."""


# Phrasing that signals advice, a recommendation, a diagnosis, or an
# opinion about a specific result - rather than a plain, generic
# description of what a test measures. This is a LANGUAGE check, not a
# medical one: it never looks at what the explanation says about the
# test itself (that's exactly what it's supposed to describe), only
# whether it strays into telling the reader what to do, or judging
# whether some result is normal/abnormal/concerning.
_ADVICE_PATTERNS = [
    r"\byou should\b",
    r"\byou (?:have|might have|may have|could have)\b",
    r"\bwe recommend\b",
    r"\bit(?:'s| is) recommended\b",
    r"\brecommend(?:ed|ation|ations)?\b",
    r"\bsee (?:a|your) doctor\b",
    r"\bconsult (?:a|your) (?:doctor|physician|healthcare provider)\b",
    r"\bseek (?:medical|immediate) (?:care|attention|help)\b",
    r"\b(?:is|are|may be|could be|might be) "
    r"(?:concerning|worrying|serious|dangerous)\b",
    r"\bindicates? (?:a|an)? ?(?:problem|condition|disease|disorder)\b",
    r"\bdiagnos(?:is|e|ed|ing)\b",
    r"\btreatment\b",
    r"\bnormal (?:range|result|value)\b",
    r"\babnormal\b",
]
_ADVICE_PATTERN = re.compile("|".join(_ADVICE_PATTERNS), re.IGNORECASE)


def contains_advice_language(text: str) -> bool:
    """
    True if the text contains any phrasing that reads as advice, a
    recommendation, a diagnosis, or a judgment about a specific result -
    rather than a plain description of what a test measures.
    """
    return bool(_ADVICE_PATTERN.search(text))


def generate_test_explanation(prompt_text: str) -> ExplanationResult:
    response = _client.messages.create(
        model=EXPLANATION_MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=SYSTEM_PROMPT,
        output_config={
            "format": {"type": "json_schema", "schema": EXPLANATION_JSON_SCHEMA}
        },
        messages=[{"role": "user", "content": prompt_text}],
    )

    if response.stop_reason == "refusal":
        raise ExplanationRefusedError("Claude declined to generate this explanation.")
    if response.stop_reason == "max_tokens":
        raise ExplanationValidationError(
            "Claude's response was truncated (hit max_tokens) - "
            "output may be incomplete and cannot be trusted."
        )

    text_blocks = [block.text for block in response.content if block.type == "text"]
    if not text_blocks:
        raise ExplanationValidationError("Claude's response contained no text content.")

    try:
        raw = json.loads(text_blocks[0])
    except json.JSONDecodeError as error:
        raise ExplanationValidationError(
            f"Claude's response was not valid JSON: {error}"
        ) from error

    try:
        result = ExplanationResult.model_validate(raw)
    except pydantic.ValidationError as error:
        raise ExplanationValidationError(
            f"Claude's response didn't match the explanation schema: {error}"
        ) from error

    if contains_advice_language(result.explanation):
        raise ExplanationValidationError(
            "Claude's explanation contained advice/diagnosis/recommendation "
            f"language, which is never allowed: {result.explanation!r}"
        )

    return result
