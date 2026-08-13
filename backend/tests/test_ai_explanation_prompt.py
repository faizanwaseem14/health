"""
Tests for the explanation prompt builder - confirms only the test name
is ever handed to Claude, never a value, range, or result.
"""

from app.ai.explanation_prompt import build_explanation_prompt


def test_prompt_includes_both_test_names():
    prompt = build_explanation_prompt("Hemoglobin", "HGB")

    assert "Hemoglobin" in prompt
    assert "HGB" in prompt


def test_prompt_never_mentions_a_value_or_range():
    # A regression guard: this prompt builder takes no value/range
    # arguments at all, so there is nothing it COULD leak - this test
    # documents that contract explicitly.
    prompt = build_explanation_prompt("Hemoglobin", "HGB")

    for leaked_field in ("13.5", "12.0-15.5", "value", "range"):
        assert leaked_field not in prompt
