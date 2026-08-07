"""
Tests for turning an in-memory OcrResult into `ocr_words` rows, and for
the result-to-OCR-word linking capability. No live database - the
`db` argument is a MagicMock and we inspect what was added to it,
exactly like the rest of this project's job-service tests.
"""

import uuid
from unittest.mock import MagicMock

from app.models import OcrWord
from app.ocr.evidence import link_result_to_ocr_words, store_ocr_evidence
from app.ocr.types import BoundingBox, OcrResult
from app.ocr.types import OcrWord as OcrWordShape

_BOX = BoundingBox.from_rectangle(0, 0, 10, 10)


def test_store_ocr_evidence_deletes_any_existing_evidence_first():
    fake_db = MagicMock()
    fake_query = MagicMock()
    fake_db.query.return_value = fake_query
    fake_query.filter.return_value = fake_query
    report_id = uuid.uuid4()

    store_ocr_evidence(
        fake_db,
        report_id=report_id,
        job_id=uuid.uuid4(),
        provider_name="tesseract",
        result=OcrResult(words=[]),
    )

    fake_db.query.assert_called_once_with(OcrWord)
    fake_query.delete.assert_called_once()


def test_store_ocr_evidence_creates_one_row_per_word_with_page_reset_word_index():
    fake_db = MagicMock()
    report_id = uuid.uuid4()
    job_id = uuid.uuid4()
    words = [
        OcrWordShape(text="A", confidence=0.9, bounding_box=_BOX, page_number=1),
        OcrWordShape(text="B", confidence=0.8, bounding_box=_BOX, page_number=1),
        OcrWordShape(text="C", confidence=0.7, bounding_box=_BOX, page_number=2),
    ]

    rows = store_ocr_evidence(
        fake_db,
        report_id=report_id,
        job_id=job_id,
        provider_name="tesseract",
        result=OcrResult(words=words),
    )

    assert [(row.page_number, row.word_index) for row in rows] == [
        (1, 0),
        (1, 1),
        (2, 0),
    ]
    for row, word in zip(rows, words):
        assert row.report_id == report_id
        assert row.job_id == job_id
        assert row.text == word.text
        assert row.confidence == word.confidence
        assert row.bounding_box == word.bounding_box.to_json()
        assert row.ocr_provider == "tesseract"

    fake_db.add_all.assert_called_once()
    fake_db.commit.assert_called_once()


def test_link_result_to_ocr_words_creates_one_link_row_per_word():
    fake_db = MagicMock()
    result_id = uuid.uuid4()
    ocr_word_ids = [uuid.uuid4(), uuid.uuid4()]

    links = link_result_to_ocr_words(
        fake_db, result_id=result_id, ocr_word_ids=ocr_word_ids
    )

    assert len(links) == 2
    assert {link.ocr_word_id for link in links} == set(ocr_word_ids)
    assert all(link.result_id == result_id for link in links)
    fake_db.add_all.assert_called_once()
    fake_db.commit.assert_called_once()
