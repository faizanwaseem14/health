"""
Tests for the results routes: listing a report's extracted results
(with their correction history and any explanation), generating
explanations on demand, and recording a correction.

Auth-required and validation-failure cases never touch the database.
The happy-path shape checks use a mocked db (query() dispatches by
which model/column was asked for, since _result_response makes several
different queries per result) - the real, end-to-end proof of this
whole flow (upload -> results -> explain -> correct -> OCR inspect)
against a real database is in the Task summary's scratch-Postgres run.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_db
from app.main import app
from app.models import Correction, Explanation, Result, ResultOcrWord, User
from app.routers.reports import require_owned_report
from app.routers.results import require_owned_result

client = TestClient(app)


def _override_auth(user, report=None, result=None):
    app.dependency_overrides[get_current_user] = lambda: user
    if report is not None:
        app.dependency_overrides[require_owned_report] = lambda: report
    if result is not None:
        app.dependency_overrides[require_owned_result] = lambda: result


def _clear_overrides():
    app.dependency_overrides.clear()


def _fake_result(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        report_id=uuid.uuid4(),
        raw_test_name="HGB",
        canonical_test_name="Hemoglobin",
        value="13.5",
        value_numeric=Decimal("13.5"),
        unit="g/dL",
        reference_range_text="12.0-15.5",
        reference_range_low=Decimal("12.0"),
        reference_range_high=Decimal("15.5"),
        flag="normal",
        ai_confidence=Decimal("0.95"),
        trust_status="trusted",
        trust_check_notes=None,
        converted_value_numeric=None,
        converted_unit=None,
        result_date="2026-01-01",
        lab_name="Fixture Regional Lab",
    )
    defaults.update(overrides)
    return Result(**defaults)


def _query_side_effect(
    *, results=None, explanation_content=None, corrections=None, ocr_links=None
):
    """Builds a db.query() side_effect that returns a different chain
    depending on which model/column it's called with - _result_response
    queries Result, Explanation.content, Correction, and ResultOcrWord
    separately."""

    def side_effect(target):
        mock = MagicMock()
        if target is Result:
            mock.filter.return_value.order_by.return_value.all.return_value = (
                results or []
            )
        elif target is Explanation.content:
            mock.filter.return_value.scalar.return_value = explanation_content
        elif target is Correction:
            mock.filter.return_value.order_by.return_value.all.return_value = (
                corrections or []
            )
        elif target is ResultOcrWord:
            mock.filter.return_value.all.return_value = ocr_links or []
        else:
            raise AssertionError(f"Unexpected db.query() target: {target!r}")
        return mock

    return side_effect


# --- GET /reports/{row_id}/results ---


def test_list_results_requires_login():
    response = client.get(f"/reports/{uuid.uuid4()}/results")

    assert response.status_code == 401


def test_list_results_rejects_someone_elses_report():
    user = User(id=uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get(f"/reports/{uuid.uuid4()}/results")
    finally:
        _clear_overrides()

    assert response.status_code in (404, 503)


def test_list_results_returns_the_full_shape_for_one_result():
    from app.models import Report

    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    result = _fake_result(report_id=report.id)
    user = User(id=uuid.uuid4())
    _override_auth(user, report=report)

    fake_db = MagicMock()
    fake_db.query.side_effect = _query_side_effect(results=[result])
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        response = client.get(f"/reports/{report.id}/results")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body) == 1
    row = body[0]
    assert row["id"] == str(result.id)
    assert row["raw_test_name"] == "HGB"
    assert row["value"] == "13.5"
    assert row["value_numeric"] == 13.5
    assert row["reference_range_low"] == 12.0
    assert row["flag"] == "normal"
    assert row["trust_status"] == "trusted"
    assert row["explanation"] is None
    assert row["corrections"] == []
    assert row["ocr_word_ids"] == []


def test_list_results_includes_explanation_and_correction_history():
    from app.models import Report

    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    result = _fake_result(report_id=report.id)
    correction = Correction(
        id=uuid.uuid4(),
        result_id=result.id,
        field_name="value",
        previous_value="13.5",
        new_value="9.5",
        reason="OCR misread",
        created_at=datetime.now(timezone.utc),
    )
    ocr_link = ResultOcrWord(
        id=uuid.uuid4(), result_id=result.id, ocr_word_id=uuid.uuid4()
    )
    user = User(id=uuid.uuid4())
    _override_auth(user, report=report)

    explanation_content = (
        "Hemoglobin measures the oxygen-carrying protein in red blood cells."
    )
    fake_db = MagicMock()
    fake_db.query.side_effect = _query_side_effect(
        results=[result],
        explanation_content=explanation_content,
        corrections=[correction],
        ocr_links=[ocr_link],
    )
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        response = client.get(f"/reports/{report.id}/results")
    finally:
        _clear_overrides()

    row = response.json()["data"][0]
    assert row["explanation"].startswith("Hemoglobin measures")
    assert len(row["corrections"]) == 1
    assert row["corrections"][0]["previous_value"] == "13.5"
    assert row["corrections"][0]["new_value"] == "9.5"
    assert row["ocr_word_ids"] == [str(ocr_link.ocr_word_id)]


# --- POST /reports/{row_id}/explanations ---


def test_generate_explanations_requires_login():
    response = client.post(f"/reports/{uuid.uuid4()}/explanations")

    assert response.status_code == 401


def test_generate_explanations_calls_the_service_and_returns_the_map():
    from app.models import Report

    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    user = User(id=uuid.uuid4())
    _override_auth(user, report=report)

    result_id = uuid.uuid4()
    fake_db = MagicMock()
    query_chain = fake_db.query.return_value.outerjoin.return_value.filter.return_value
    query_chain.all.return_value = [
        (result_id, "Hemoglobin measures oxygen-carrying capacity.")
    ]
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        with patch(
            "app.routers.results.generate_explanations_for_report"
        ) as mock_generate:
            response = client.post(f"/reports/{report.id}/explanations")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    mock_generate.assert_called_once_with(fake_db, report)
    assert response.json()["data"] == {
        str(result_id): "Hemoglobin measures oxygen-carrying capacity."
    }


# --- POST /results/{row_id}/corrections ---


def test_create_correction_requires_login():
    response = client.post(
        f"/results/{uuid.uuid4()}/corrections",
        json={"field_name": "value", "new_value": "9.5"},
    )

    assert response.status_code == 401


def test_create_correction_rejects_someone_elses_result():
    user = User(id=uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.post(
            f"/results/{uuid.uuid4()}/corrections",
            json={"field_name": "value", "new_value": "9.5"},
        )
    finally:
        _clear_overrides()

    assert response.status_code in (404, 503)


def test_create_correction_rejects_an_uncorrectable_field():
    result = _fake_result()
    user = User(id=uuid.uuid4())
    _override_auth(user, result=result)

    try:
        response = client.post(
            f"/results/{result.id}/corrections",
            json={"field_name": "trust_status", "new_value": "trusted"},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 422


def test_create_correction_updates_the_value_and_recomputes_the_flag():
    # 9.5 is below the printed 12.0-15.5 range, so the flag must flip
    # from "normal" to "low" - proves the correction endpoint reuses
    # the same deterministic status calculation as a fresh extraction.
    result = _fake_result(value="13.5", flag="normal")
    user = User(id=uuid.uuid4())
    _override_auth(user, result=result)

    fake_db = MagicMock()
    fake_db.query.side_effect = _query_side_effect(results=[result])
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        response = client.post(
            f"/results/{result.id}/corrections",
            json={"field_name": "value", "new_value": "9.5", "reason": "misread"},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 201
    # The route also adds an AuditLog entry afterward (record_audit_event) -
    # the Correction is specifically the FIRST thing added.
    added_correction = fake_db.add.call_args_list[0][0][0]
    assert isinstance(added_correction, Correction)
    assert added_correction.previous_value == "13.5"
    assert added_correction.new_value == "9.5"
    assert added_correction.reason == "misread"

    assert result.value == "9.5"
    assert result.flag == "low"
    assert float(result.value_numeric) == 9.5
