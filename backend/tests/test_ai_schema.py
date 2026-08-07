"""
Tests for the strict extraction schema itself - the validation rules
that make "reject malformed AI output" actually enforceable.
"""

import pytest
from pydantic import ValidationError

from app.ai.schema import ExtractedTestRow, ExtractionResult


def _valid_row(**overrides):
    row = {
        "raw_test_name": "HGB",
        "canonical_test_name": "Hemoglobin",
        "value": "13.5",
        "unit": "g/dL",
        "reference_range": "12.0-15.5",
        "date": "2026-01-01",
        "lab": "Acme Labs",
        "evidence_word_indices": [0, 1, 2],
        "confidence": 0.95,
    }
    row.update(overrides)
    return row


def test_a_fully_populated_row_validates():
    row = ExtractedTestRow.model_validate(_valid_row())

    assert row.raw_test_name == "HGB"
    assert row.confidence == 0.95


def test_nullable_fields_can_be_none():
    row = ExtractedTestRow.model_validate(
        _valid_row(unit=None, reference_range=None, date=None, lab=None)
    )

    assert row.unit is None
    assert row.reference_range is None


def test_missing_required_field_is_rejected():
    payload = _valid_row()
    del payload["raw_test_name"]

    with pytest.raises(ValidationError):
        ExtractedTestRow.model_validate(payload)


def test_confidence_outside_0_to_1_is_rejected():
    with pytest.raises(ValidationError):
        ExtractedTestRow.model_validate(_valid_row(confidence=1.5))

    with pytest.raises(ValidationError):
        ExtractedTestRow.model_validate(_valid_row(confidence=-0.1))


def test_empty_string_test_name_is_rejected():
    with pytest.raises(ValidationError):
        ExtractedTestRow.model_validate(_valid_row(raw_test_name=""))


def test_unknown_extra_field_is_rejected():
    # The core "strict" requirement: Claude adding a field we didn't
    # ask for must not silently pass through.
    with pytest.raises(ValidationError):
        ExtractedTestRow.model_validate(_valid_row(made_up_field="surprise"))


def test_extraction_result_defaults_to_an_empty_row_list():
    result = ExtractionResult.model_validate({"rows": []})

    assert result.rows == []


def test_extraction_result_rejects_unknown_top_level_field():
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate({"rows": [], "summary": "not allowed"})
