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

import anthropic
import httpx

from app.ai.explanation import ExplanationRefusedError, ExplanationValidationError
from app.ai.explanation_prompt import CORRECTION_NOTE
from app.ai.explanation_schema import ExplanationResult
from app.ai.explanation_service import MAX_ATTEMPTS, generate_explanations_for_report
from app.models import Report, Result


def _connection_error():
    return anthropic.APIConnectionError(request=httpx.Request("POST", "http://x"))


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


# --- retry behavior ---


def test_a_validation_failure_retries_with_a_correction_note_and_can_succeed():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    results = [_result(report.id, "Hemoglobin")]
    fake_db = _fake_db(results)

    with patch(
        "app.ai.explanation_service.generate_test_explanation",
        side_effect=[
            ExplanationValidationError("advice language detected"),
            ExplanationResult(explanation="A plain description."),
        ],
    ) as mock_generate:
        generate_explanations_for_report(fake_db, report)

    added = [call.args[0] for call in fake_db.add.call_args_list]
    assert len(added) == 1
    assert added[0].content == "A plain description."
    # The retry's prompt names the mistake, so the model gets a real
    # chance to self-correct instead of repeating the same answer.
    assert mock_generate.call_count == 2
    second_prompt = mock_generate.call_args_list[1].args[0]
    assert CORRECTION_NOTE in second_prompt


def test_gives_up_after_max_attempts_of_repeated_validation_failures():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    results = [_result(report.id, "Hemoglobin")]
    fake_db = _fake_db(results)

    with patch(
        "app.ai.explanation_service.generate_test_explanation",
        side_effect=ExplanationValidationError("advice language detected"),
    ) as mock_generate:
        generate_explanations_for_report(fake_db, report)

    fake_db.add.assert_not_called()
    assert mock_generate.call_count == MAX_ATTEMPTS


def test_a_transient_api_error_is_retried_and_can_succeed():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    results = [_result(report.id, "Hemoglobin")]
    fake_db = _fake_db(results)

    with (
        patch("app.ai.explanation_service.time.sleep") as mock_sleep,
        patch(
            "app.ai.explanation_service.generate_test_explanation",
            side_effect=[
                _connection_error(),
                ExplanationResult(explanation="A plain description."),
            ],
        ) as mock_generate,
    ):
        generate_explanations_for_report(fake_db, report)

    added = [call.args[0] for call in fake_db.add.call_args_list]
    assert len(added) == 1
    assert mock_generate.call_count == 2
    mock_sleep.assert_called_once()  # backed off before the retry


def test_a_refusal_is_not_retried():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    results = [_result(report.id, "Hemoglobin")]
    fake_db = _fake_db(results)

    with patch(
        "app.ai.explanation_service.generate_test_explanation",
        side_effect=ExplanationRefusedError("declined"),
    ) as mock_generate:
        generate_explanations_for_report(fake_db, report)

    fake_db.add.assert_not_called()
    # A refusal is a policy decision, not worth retrying identically.
    mock_generate.assert_called_once()


def test_an_unexpected_error_for_one_test_name_does_not_block_another():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    results = [
        _result(report.id, "Hemoglobin"),
        _result(report.id, "Glucose"),
    ]
    fake_db = _fake_db(results)

    def fake_generate_one(canonical_test_name, raw_test_name):
        if canonical_test_name == "Hemoglobin":
            raise RuntimeError("something nobody anticipated")
        return "Glucose is a sugar in the blood."

    with patch(
        "app.ai.explanation_service._generate_one_explanation",
        side_effect=fake_generate_one,
    ):
        generate_explanations_for_report(fake_db, report)

    added = [call.args[0] for call in fake_db.add.call_args_list]
    assert len(added) == 1
    assert added[0].content == "Glucose is a sugar in the blood."
