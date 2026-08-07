"""
Tests for the OCR_PROVIDER config-driven factory and the
download-from-R2 -> extract -> store-evidence orchestration. R2 and the
OCR provider are both mocked - what's under test here is the wiring,
not either of those pieces individually (see test_storage.py,
test_ocr_provider_shape.py, and test_ocr_evidence.py for those).
"""

import uuid
from unittest.mock import MagicMock, patch

from app.config import settings
from app.models import Report
from app.ocr.google_vision_provider import GoogleVisionProvider
from app.ocr.service import get_active_provider, run_ocr_for_report
from app.ocr.tesseract_provider import TesseractProvider
from app.ocr.types import BoundingBox, OcrResult
from app.ocr.types import OcrWord as OcrWordShape


def _with_ocr_provider(value: str):
    class _Patch:
        def __enter__(self):
            self.original = settings.ocr_provider
            object.__setattr__(settings, "ocr_provider", value)
            return settings

        def __exit__(self, *exc_info):
            object.__setattr__(settings, "ocr_provider", self.original)

    return _Patch()


def test_get_active_provider_defaults_to_tesseract():
    with _with_ocr_provider("tesseract"):
        assert isinstance(get_active_provider(), TesseractProvider)


def test_get_active_provider_returns_google_vision_when_selected():
    with _with_ocr_provider("google_vision"):
        assert isinstance(get_active_provider(), GoogleVisionProvider)


def test_run_ocr_for_report_downloads_extracts_and_stores_evidence():
    fake_db = MagicMock()
    report = Report(id=uuid.uuid4(), storage_key="reports/some-profile/some-file.png")
    job_id = uuid.uuid4()
    fake_bytes = b"fake file bytes"
    fake_result = OcrResult(
        words=[
            OcrWordShape(
                text="Hi",
                confidence=0.9,
                bounding_box=BoundingBox.from_rectangle(0, 0, 1, 1),
                page_number=1,
            )
        ]
    )

    with (
        patch(
            "app.ocr.service.download_file_bytes", return_value=fake_bytes
        ) as mock_download,
        patch("app.ocr.service.get_active_provider") as mock_get_provider,
        patch("app.ocr.service.store_ocr_evidence") as mock_store,
    ):
        mock_provider = MagicMock()
        mock_provider.extract.return_value = fake_result
        mock_get_provider.return_value = mock_provider

        result = run_ocr_for_report(fake_db, report, job_id)

    mock_download.assert_called_once_with(report.storage_key)
    mock_provider.extract.assert_called_once_with(fake_bytes)
    mock_store.assert_called_once_with(
        fake_db,
        report_id=report.id,
        job_id=job_id,
        provider_name=settings.ocr_provider,
        result=fake_result,
    )
    assert result is fake_result
