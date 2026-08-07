"""
Tests for the Claude call itself: does it correctly turn a mocked
response into a validated ExtractionResult, and correctly reject
everything that isn't one? No real network call or API key needed -
app.ai.extraction._client.messages.create is mocked directly.
"""

import json
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from app.ai.extraction import (
    ExtractionRefusedError,
    ExtractionValidationError,
    extract_structured_rows,
)

_VALID_ROWS_JSON = json.dumps(
    {
        "rows": [
            {
                "raw_test_name": "HGB",
                "canonical_test_name": "Hemoglobin",
                "value": "13.5",
                "unit": "g/dL",
                "reference_range": "12.0-15.5",
                "date": None,
                "lab": None,
                "evidence_word_indices": [0, 1],
                "confidence": 0.9,
            }
        ]
    }
)


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


def _fake_response(*, stop_reason: str, text: str | None = None):
    response = MagicMock()
    response.stop_reason = stop_reason
    response.content = [_FakeTextBlock(text=text)] if text is not None else []
    return response


def test_returns_a_validated_result_for_a_normal_successful_response():
    with patch(
        "app.ai.extraction._client.messages.create",
        return_value=_fake_response(stop_reason="end_turn", text=_VALID_ROWS_JSON),
    ):
        result = extract_structured_rows("[0] (page 1) HGB\n[1] (page 1) 13.5")

    assert len(result.rows) == 1
    assert result.rows[0].raw_test_name == "HGB"
    assert result.rows[0].evidence_word_indices == [0, 1]


def test_returns_an_empty_result_when_claude_finds_nothing():
    empty_json = json.dumps({"rows": []})
    with patch(
        "app.ai.extraction._client.messages.create",
        return_value=_fake_response(stop_reason="end_turn", text=empty_json),
    ):
        result = extract_structured_rows("[0] (page 1) SomeHeaderText")

    assert result.rows == []


def test_refusal_raises_extraction_refused_error():
    with patch(
        "app.ai.extraction._client.messages.create",
        return_value=_fake_response(stop_reason="refusal"),
    ):
        with pytest.raises(ExtractionRefusedError):
            extract_structured_rows("some text")


def test_max_tokens_raises_extraction_validation_error():
    # Truncated output is never trusted, even if what came back so far
    # happens to be syntactically valid JSON.
    with patch(
        "app.ai.extraction._client.messages.create",
        return_value=_fake_response(stop_reason="max_tokens", text=_VALID_ROWS_JSON),
    ):
        with pytest.raises(ExtractionValidationError, match="truncated"):
            extract_structured_rows("some text")


def test_no_text_content_raises_extraction_validation_error():
    with patch(
        "app.ai.extraction._client.messages.create",
        return_value=_fake_response(stop_reason="end_turn"),
    ):
        with pytest.raises(ExtractionValidationError, match="no text content"):
            extract_structured_rows("some text")


def test_invalid_json_raises_extraction_validation_error():
    with patch(
        "app.ai.extraction._client.messages.create",
        return_value=_fake_response(stop_reason="end_turn", text="not { json"),
    ):
        with pytest.raises(ExtractionValidationError, match="not valid JSON"):
            extract_structured_rows("some text")


def test_json_that_does_not_match_the_schema_raises_extraction_validation_error():
    # Valid JSON, but missing required fields - a bad row, not bad text.
    bad_json = json.dumps({"rows": [{"raw_test_name": "HGB"}]})
    with patch(
        "app.ai.extraction._client.messages.create",
        return_value=_fake_response(stop_reason="end_turn", text=bad_json),
    ):
        with pytest.raises(ExtractionValidationError, match="didn't match"):
            extract_structured_rows("some text")


def test_sends_the_word_list_and_json_schema_format():
    with patch(
        "app.ai.extraction._client.messages.create",
        return_value=_fake_response(stop_reason="end_turn", text=_VALID_ROWS_JSON),
    ) as mock_create:
        extract_structured_rows("[0] (page 1) HGB")

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["messages"] == [{"role": "user", "content": "[0] (page 1) HGB"}]
    assert call_kwargs["output_config"]["format"]["type"] == "json_schema"
    assert "rows" in call_kwargs["output_config"]["format"]["schema"]["properties"]
