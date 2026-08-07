"""
Tests for turning a validated ExtractionResult into Result rows and
OCR-word evidence links. No live database - db is a MagicMock and we
inspect what was added to it, same pattern as test_ocr_evidence.py.
extract_structured_rows itself is mocked (see test_ai_extraction.py for
its own tests).
"""

import uuid
from unittest.mock import MagicMock, patch

from app.ai.schema import ExtractedTestRow, ExtractionResult
from app.ai.service import run_extraction_for_report
from app.models import OcrWord, Report, Result


def _ocr_word(word_id, page_number=1, word_index=0):
    return OcrWord(
        id=word_id,
        report_id=uuid.uuid4(),
        page_number=page_number,
        word_index=word_index,
        text="word",
        confidence=0.9,
        bounding_box=[[0, 0], [1, 0], [1, 1], [0, 1]],
        ocr_provider="tesseract",
    )


def _configure_query_chain(fake_db, ocr_words):
    chain = fake_db.query.return_value.filter.return_value.order_by.return_value
    chain.all.return_value = ocr_words


def test_run_extraction_for_report_stores_one_result_row_per_extracted_row():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    job_id = uuid.uuid4()
    word_ids = [uuid.uuid4(), uuid.uuid4()]
    ocr_words = [_ocr_word(word_ids[0]), _ocr_word(word_ids[1])]

    fake_db = MagicMock()
    _configure_query_chain(fake_db, ocr_words)

    extraction_result = ExtractionResult(
        rows=[
            ExtractedTestRow(
                raw_test_name="HGB",
                canonical_test_name="Hemoglobin",
                value="13.5",
                unit="g/dL",
                reference_range="12.0-15.5",
                date="2026-01-01",
                lab="Acme Labs",
                evidence_word_indices=[0, 1],
                confidence=0.9,
            )
        ]
    )

    with (
        patch("app.ai.service.extract_structured_rows", return_value=extraction_result),
        patch("app.ai.service.link_result_to_ocr_words") as mock_link,
    ):
        result = run_extraction_for_report(fake_db, report, job_id)

    assert result is extraction_result

    added_results = [call.args[0] for call in fake_db.add.call_args_list]
    assert len(added_results) == 1
    stored = added_results[0]
    assert isinstance(stored, Result)
    assert stored.report_id == report.id
    assert stored.job_id == job_id
    assert stored.raw_test_name == "HGB"
    assert stored.canonical_test_name == "Hemoglobin"
    assert stored.value == "13.5"
    assert stored.unit == "g/dL"
    assert stored.reference_range_text == "12.0-15.5"
    assert stored.result_date == "2026-01-01"
    assert stored.lab_name == "Acme Labs"
    assert stored.ai_confidence == 0.9

    # Evidence indices [0, 1] resolve to the actual OcrWord ids, in order.
    mock_link.assert_called_once()
    _, link_kwargs = mock_link.call_args
    assert link_kwargs["ocr_word_ids"] == word_ids

    assert report.extraction_model == "claude-haiku-4-5"
    assert report.extraction_prompt_version == "v1"


def test_deletes_any_previous_extraction_before_storing_new_rows():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    fake_db = MagicMock()
    _configure_query_chain(fake_db, [])

    with patch(
        "app.ai.service.extract_structured_rows",
        return_value=ExtractionResult(rows=[]),
    ):
        run_extraction_for_report(fake_db, report, uuid.uuid4())

    fake_db.query.assert_any_call(Result)


def test_out_of_range_evidence_indices_are_silently_dropped():
    # A malformed index shouldn't crash storage - the row itself is
    # still real and worth keeping; it just has less evidence attached.
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    ocr_words = [_ocr_word(uuid.uuid4())]
    fake_db = MagicMock()
    _configure_query_chain(fake_db, ocr_words)

    extraction_result = ExtractionResult(
        rows=[
            ExtractedTestRow(
                raw_test_name="HGB",
                canonical_test_name="Hemoglobin",
                value="13.5",
                evidence_word_indices=[0, 99],
                confidence=0.9,
            )
        ]
    )

    with (
        patch("app.ai.service.extract_structured_rows", return_value=extraction_result),
        patch("app.ai.service.link_result_to_ocr_words") as mock_link,
    ):
        run_extraction_for_report(fake_db, report, uuid.uuid4())

    mock_link.assert_called_once()
    _, link_kwargs = mock_link.call_args
    assert link_kwargs["ocr_word_ids"] == [ocr_words[0].id]


def test_a_row_with_no_evidence_indices_stores_the_row_without_linking():
    report = Report(id=uuid.uuid4(), storage_key="reports/x/y.png")
    fake_db = MagicMock()
    _configure_query_chain(fake_db, [])

    extraction_result = ExtractionResult(
        rows=[
            ExtractedTestRow(
                raw_test_name="HGB",
                canonical_test_name="Hemoglobin",
                value="13.5",
                evidence_word_indices=[],
                confidence=0.5,
            )
        ]
    )

    with (
        patch("app.ai.service.extract_structured_rows", return_value=extraction_result),
        patch("app.ai.service.link_result_to_ocr_words") as mock_link,
    ):
        run_extraction_for_report(fake_db, report, uuid.uuid4())

    mock_link.assert_not_called()
    assert fake_db.add.call_count == 1
