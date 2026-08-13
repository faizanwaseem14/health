"""
Tests for generate_explanations_for_report (app/ai/explanation_service.py) -
the orchestration that generates one plain-language explanation per
result, deduplicating Claude calls by canonical_test_name. No live
database, no live Claude call - db is a MagicMock and
generate_test_explanation is mocked, same pattern as
test_ai_service.py.
"""

import uuid
from unittest.mock import MagicMock, patch

from app.ai.explanation import ExplanationRefusedError, ExplanationValidationError
from app.ai.explanation_schema import ExplanationResult
from app.ai.explanation_service import generate_explanations_for_report
from app.models import Report, Result


def _result(report_id, canonical_test_name, raw_test_name="HGB"):
    return Result(
        id=uuid.uuid4(),
        report_id=report_id,
        raw_test_name=raw_test_name,
        canonical_test_name=canonical_test_name,
        value="13.5",
    )


def _fake_db(results):
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.all.return_value = results
    return fake_db


def test_stores_one_explanation_per_result_row():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    results = [_result(report.id, "Hemoglobin"), _result(report.id, "Glucose")]
    fake_db = _fake_db(results)

    with patch(
        "app.ai.explanation_service.generate_test_explanation",
        return_value=ExplanationResult(explanation="A plain description."),
    ) as mock_generate:
        generate_explanations_for_report(fake_db, report)

    added = [call.args[0] for call in fake_db.add.call_args_list]
    assert len(added) == 2
    assert {row.result_id for row in added} == {r.id for r in results}
    assert all(row.content == "A plain description." for row in added)
    assert mock_generate.call_count == 2  # two distinct test names


def test_deduplicates_claude_calls_for_the_same_test_name():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    # Same test printed three times in one report (e.g. a repeated panel).
    results = [_result(report.id, "Hemoglobin") for _ in range(3)]
    fake_db = _fake_db(results)

    with patch(
        "app.ai.explanation_service.generate_test_explanation",
        return_value=ExplanationResult(explanation="A plain description."),
    ) as mock_generate:
        generate_explanations_for_report(fake_db, report)

    # Only ONE Claude call for three rows of the same test name...
    mock_generate.assert_called_once()
    # ...but every row still gets its own Explanation row.
    assert fake_db.add.call_count == 3


def test_a_refused_explanation_is_skipped_not_raised():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    results = [_result(report.id, "Hemoglobin")]
    fake_db = _fake_db(results)

    with patch(
        "app.ai.explanation_service.generate_test_explanation",
        side_effect=ExplanationRefusedError("declined"),
    ):
        generate_explanations_for_report(fake_db, report)

    fake_db.add.assert_not_called()
    fake_db.commit.assert_called_once()


def test_a_validation_failure_for_one_test_does_not_block_another():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    results = [
        _result(report.id, "Hemoglobin"),
        _result(report.id, "Glucose"),
    ]
    fake_db = _fake_db(results)

    def fake_generate(prompt_text):
        if "Hemoglobin" in prompt_text:
            raise ExplanationValidationError("advice language detected")
        return ExplanationResult(explanation="Glucose is a sugar in the blood.")

    with patch(
        "app.ai.explanation_service.generate_test_explanation",
        side_effect=fake_generate,
    ):
        generate_explanations_for_report(fake_db, report)

    added = [call.args[0] for call in fake_db.add.call_args_list]
    assert len(added) == 1
    assert added[0].content == "Glucose is a sugar in the blood."


def test_deletes_any_previous_explanations_before_storing_new_ones():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    fake_db = _fake_db([])

    generate_explanations_for_report(fake_db, report)

    fake_db.query.assert_any_call(Result.id)
