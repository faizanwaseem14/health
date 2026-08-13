"""
Tests for the strict explanation schema itself.
"""

import pytest
from pydantic import ValidationError

from app.ai.explanation_schema import ExplanationResult


def test_a_valid_explanation_validates():
    result = ExplanationResult.model_validate(
        {"explanation": "Hemoglobin is a protein in red blood cells."}
    )
    assert result.explanation == "Hemoglobin is a protein in red blood cells."


def test_missing_explanation_field_is_rejected():
    with pytest.raises(ValidationError):
        ExplanationResult.model_validate({})


def test_empty_string_explanation_is_rejected():
    with pytest.raises(ValidationError):
        ExplanationResult.model_validate({"explanation": ""})


def test_unknown_extra_field_is_rejected():
    with pytest.raises(ValidationError):
        ExplanationResult.model_validate(
            {"explanation": "Some text.", "advice": "see a doctor"}
        )
