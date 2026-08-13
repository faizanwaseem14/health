"""
Tests for the Claude call itself: does it correctly turn a mocked
response into a validated ExplanationResult, correctly reject
everything that isn't one, and - critically - reject any response that
contains advice/diagnosis/recommendation language even when it's
otherwise a perfectly valid, schema-matching response? No real network
call or API key needed - app.ai.explanation._client.messages.create is
mocked directly, same pattern as test_ai_extraction.py.
"""

import json
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from app.ai.explanation import (
    ExplanationRefusedError,
    ExplanationValidationError,
    contains_advice_language,
    generate_test_explanation,
)

_VALID_EXPLANATION_JSON = json.dumps(
    {"explanation": "Hemoglobin is a protein in red blood cells that carries oxygen."}
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
        "app.ai.explanation._client.messages.create",
        return_value=_fake_response(
            stop_reason="end_turn", text=_VALID_EXPLANATION_JSON
        ),
    ):
        result = generate_test_explanation("Test name: Hemoglobin")

    assert "protein" in result.explanation


def test_refusal_raises_explanation_refused_error():
    with patch(
        "app.ai.explanation._client.messages.create",
        return_value=_fake_response(stop_reason="refusal"),
    ):
        with pytest.raises(ExplanationRefusedError):
            generate_test_explanation("some text")


def test_max_tokens_raises_explanation_validation_error():
    with patch(
        "app.ai.explanation._client.messages.create",
        return_value=_fake_response(
            stop_reason="max_tokens", text=_VALID_EXPLANATION_JSON
        ),
    ):
        with pytest.raises(ExplanationValidationError, match="truncated"):
            generate_test_explanation("some text")


def test_no_text_content_raises_explanation_validation_error():
    with patch(
        "app.ai.explanation._client.messages.create",
        return_value=_fake_response(stop_reason="end_turn"),
    ):
        with pytest.raises(ExplanationValidationError, match="no text content"):
            generate_test_explanation("some text")


def test_invalid_json_raises_explanation_validation_error():
    with patch(
        "app.ai.explanation._client.messages.create",
        return_value=_fake_response(stop_reason="end_turn", text="not { json"),
    ):
        with pytest.raises(ExplanationValidationError, match="not valid JSON"):
            generate_test_explanation("some text")


def test_json_that_does_not_match_the_schema_raises_explanation_validation_error():
    bad_json = json.dumps({"wrong_field": "oops"})
    with patch(
        "app.ai.explanation._client.messages.create",
        return_value=_fake_response(stop_reason="end_turn", text=bad_json),
    ):
        with pytest.raises(ExplanationValidationError, match="didn't match"):
            generate_test_explanation("some text")


def test_sends_the_prompt_and_json_schema_format():
    with patch(
        "app.ai.explanation._client.messages.create",
        return_value=_fake_response(
            stop_reason="end_turn", text=_VALID_EXPLANATION_JSON
        ),
    ) as mock_create:
        generate_test_explanation("Test name: Hemoglobin")

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["messages"] == [
        {"role": "user", "content": "Test name: Hemoglobin"}
    ]
    assert call_kwargs["output_config"]["format"]["type"] == "json_schema"
    assert (
        "explanation" in call_kwargs["output_config"]["format"]["schema"]["properties"]
    )


# --- the advice-language guard: the core requirement of task 21 ---


@pytest.mark.parametrize(
    "advice_text",
    [
        "Hemoglobin carries oxygen. You should see a doctor if it's low.",
        "This test measures glucose. We recommend fasting before testing.",
        "Cholesterol is a fat in the blood. High cholesterol is concerning.",
        "This measures white blood cells, which can indicate a condition.",
        "A creatinine test checks kidney function; consult your doctor for treatment.",
        "This is used to diagnose diabetes.",
        "A normal range for this test is considered healthy.",
    ],
)
def test_a_response_with_advice_language_is_rejected_even_if_schema_valid(advice_text):
    advice_json = json.dumps({"explanation": advice_text})
    with patch(
        "app.ai.explanation._client.messages.create",
        return_value=_fake_response(stop_reason="end_turn", text=advice_json),
    ):
        with pytest.raises(ExplanationValidationError, match="advice"):
            generate_test_explanation("Test name: Hemoglobin")


@pytest.mark.parametrize(
    "clean_text",
    [
        "Hemoglobin is a protein in red blood cells that carries oxygen.",
        "Glucose is a type of sugar in the blood, used by the body for energy.",
        "This test measures the amount of cholesterol, a type of fat, in the blood.",
        "White blood cells are part of the immune system that fights infection.",
    ],
)
def test_purely_descriptive_explanations_pass_the_advice_language_guard(clean_text):
    assert contains_advice_language(clean_text) is False


@pytest.mark.parametrize(
    "advice_text",
    [
        "You should consult your doctor.",
        "This result is abnormal.",
        "This may indicate a condition that needs treatment.",
        "We recommend follow-up testing.",
    ],
)
def test_contains_advice_language_detects_advice_phrasing_directly(advice_text):
    assert contains_advice_language(advice_text) is True
