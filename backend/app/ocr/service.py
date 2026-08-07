"""
Picks the active OCR provider from config, and orchestrates running it
against a report's original file: download from R2, run OCR, store the
result as evidence. This is the ONE place that knows both "which
provider is active" and "what a report/job actually is" - providers
themselves know neither.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Report
from app.ocr.evidence import store_ocr_evidence
from app.ocr.google_vision_provider import GoogleVisionProvider
from app.ocr.provider import OcrProvider
from app.ocr.tesseract_provider import TesseractProvider
from app.ocr.types import OcrResult
from app.storage.r2 import download_file_bytes

# The one place OCR_PROVIDER's string value maps to an actual
# implementation - add a new provider here (and nowhere else needs to
# change) when a third engine is ever supported.
_PROVIDERS: dict[str, type[OcrProvider]] = {
    "tesseract": TesseractProvider,
    "google_vision": GoogleVisionProvider,
}


def get_active_provider() -> OcrProvider:
    """
    Builds whichever provider OCR_PROVIDER (backend/.env) selects.
    config.py already validates OCR_PROVIDER is one of _PROVIDERS'
    keys at startup, so a lookup miss here would mean the two have
    drifted out of sync - a bug worth a loud KeyError, not a silent
    fallback.
    """
    return _PROVIDERS[settings.ocr_provider]()


def run_ocr_for_report(db: Session, report: Report, job_id: UUID) -> OcrResult:
    """
    Downloads the report's original file from R2 (never modifies it),
    runs it through the active provider, and stores the result as
    durable evidence. Returns the OcrResult so the caller (the worker)
    can decide the job's outcome from it.
    """
    file_bytes = download_file_bytes(report.storage_key)
    provider = get_active_provider()
    result = provider.extract(file_bytes)
    store_ocr_evidence(
        db,
        report_id=report.id,
        job_id=job_id,
        provider_name=settings.ocr_provider,
        result=result,
    )
    return result
