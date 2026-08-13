"""
Tests for run_trust_checks_for_report (app/trust/service.py) - the
orchestration that runs every check against every result in a report and
records "trusted" vs "review_required". No live database - db is a
MagicMock, same pattern as test_ai_service.py. The individual checks
themselves are tested for real in test_trust_checks.py; here we only
prove the wiring: which check ran, which value it saw, and how its
pass/fail result gets recorded and aggregated.

settings.trust_confidence_threshold is patched to a known value (0.8) so
these tests don't depend on whatever TRUST_CONFIDENCE_THRESHOLD happens
to be set to in the environment they run in.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models import OcrWord, Result
from app.trust.service import (
    NEEDS_REVIEW,
    TRUSTED,
    run_trust_checks_for_report,
)


def _ocr_word(text, word_index=0, page_number=1):
    return OcrWord(
        id=uuid.uuid4(),
        report_id=uuid.uuid4(),
        page_number=page_number,
        word_index=word_index,
        text=text,
        confidence=0.9,
        bounding_box=[[0, 0], [1, 0], [1, 1], [0, 1]],
        ocr_provider="tesseract",
    )


def _result(
    value="13.5",
    unit="g/dL",
    reference_range_text="12.0-15.5",
    ai_confidence=0.9,
):
    return Result(
        id=uuid.uuid4(),
        report_id=uuid.uuid4(),
        raw_test_name="HGB",
        value=value,
        unit=unit,
        reference_range_text=reference_range_text,
        ai_confidence=ai_confidence,
    )


def _fake_db(results, evidence_words):
    """
    A MagicMock db where db.query(Result)...all() returns `results` and
    db.query(OcrWord)...all() (the evidence lookup) returns
    `evidence_words` - fine for these tests since each one only ever
    resolves evidence for a single result at a time.
    """
    fake_db = MagicMock()

    def query_side_effect(model):
        mock = MagicMock()
        if model is Result:
            mock.filter.return_value.all.return_value = results
        elif model is OcrWord:
            chain = mock.join.return_value.filter.return_value.order_by.return_value
            chain.all.return_value = evidence_words
        return mock

    fake_db.query.side_effect = query_side_effect
    return fake_db


def _run_with_threshold(fake_db, report_id, threshold=0.8):
    with patch(
        "app.trust.service.settings",
        SimpleNamespace(trust_confidence_threshold=threshold),
    ):
        return run_trust_checks_for_report(fake_db, report_id)


def test_a_value_that_is_in_evidence_and_well_formed_is_trusted():
    result = _result(value="13.5")
    fake_db = _fake_db([result], [_ocr_word("HGB 13.5 g/dL")])

    all_trusted = _run_with_threshold(fake_db, result.report_id)

    assert all_trusted is True
    assert result.trust_status == TRUSTED
    assert result.trust_check_notes is None
    fake_db.commit.assert_called_once()


def test_a_value_that_is_not_in_evidence_is_routed_to_review():
    # The anti-hallucination guard: the AI claimed 99.9, but the OCR
    # evidence it cited only actually says 13.5.
    result = _result(value="99.9")
    fake_db = _fake_db([result], [_ocr_word("HGB 13.5 g/dL")])

    all_trusted = _run_with_threshold(fake_db, result.report_id)

    assert all_trusted is False
    assert result.trust_status == NEEDS_REVIEW
    assert "99.9" in result.trust_check_notes


def test_a_malformed_value_is_routed_to_review_even_when_traceable():
    # The value IS present verbatim in its own evidence (so the
    # anti-hallucination check alone would pass) but it doesn't parse as
    # a number - proving a single failing check is enough, independent
    # of every other check passing.
    result = _result(value="13..5x")
    fake_db = _fake_db([result], [_ocr_word("HGB 13..5x g/dL")])

    all_trusted = _run_with_threshold(fake_db, result.report_id)

    assert all_trusted is False
    assert result.trust_status == NEEDS_REVIEW
    assert "13..5x" in result.trust_check_notes


def test_a_low_confidence_value_is_routed_to_review():
    # Everything else about the row is clean - only its confidence is
    # below the configured threshold.
    result = _result(value="13.5", ai_confidence=0.5)
    fake_db = _fake_db([result], [_ocr_word("HGB 13.5 g/dL")])

    all_trusted = _run_with_threshold(fake_db, result.report_id, threshold=0.8)

    assert all_trusted is False
    assert result.trust_status == NEEDS_REVIEW
    assert "0.50" in result.trust_check_notes
    assert "0.80" in result.trust_check_notes


def test_a_report_is_only_fully_trusted_when_every_result_passes():
    trusted_result = _result(value="13.5")
    review_result = _result(value="99.9")
    report_id = trusted_result.report_id
    review_result.report_id = report_id

    fake_db = _fake_db([trusted_result, review_result], [_ocr_word("HGB 13.5 g/dL")])

    all_trusted = _run_with_threshold(fake_db, report_id)

    # The whole report is not fully trusted...
    assert all_trusted is False
    # ...but each row's own status was decided independently, not
    # dragged down or up by the other row.
    assert trusted_result.trust_status == TRUSTED
    assert review_result.trust_status == NEEDS_REVIEW


def test_a_report_with_zero_results_is_vacuously_fully_trusted():
    fake_db = _fake_db([], [])

    all_trusted = _run_with_threshold(fake_db, uuid.uuid4())

    assert all_trusted is True
