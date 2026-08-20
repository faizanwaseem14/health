"""
Routes for inspecting a report's OCR evidence: the raw words + bounding
boxes OCR produced, and the exact page image they were read from - lets
someone compare an extracted value against precisely where it came from
on the original page.
"""

import io

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db
from app.core.responses import success_response
from app.models import OcrWord, Report
from app.ocr.image_utils import load_image_pages
from app.routers.reports import require_owned_report
from app.storage.r2 import download_file_bytes

router = APIRouter()


@router.get("/reports/{row_id}/ocr-words")
def list_ocr_words(
    report: Report = Depends(require_owned_report),
    db: Session = Depends(get_db),
):
    """PROTECTED route: every OCR word for a report, in reading order."""
    words = (
        db.query(OcrWord)
        .filter(OcrWord.report_id == report.id)
        .order_by(OcrWord.page_number, OcrWord.word_index)
        .all()
    )
    data = [
        {
            "id": str(word.id),
            "page_number": word.page_number,
            "word_index": word.word_index,
            "text": word.text,
            "confidence": float(word.confidence),
            "bounding_box": word.bounding_box,
        }
        for word in words
    ]
    return success_response(data)


@router.get("/reports/{row_id}/pages/{page_number}")
def get_report_page_image(
    page_number: int,
    report: Report = Depends(require_owned_report),
):
    """
    PROTECTED route: renders one page of the report's ORIGINAL file as
    a PNG, at the exact resolution/orientation OCR itself ran against
    (same app/ocr/image_utils.py used for OCR) - so a page's ocr_words
    bounding box pixel coordinates line up correctly when overlaid on
    this image. Re-renders on every request rather than caching a copy
    - the simplest correct thing at this scale (an inspection screen
    someone opens occasionally, not a hot path).
    """
    file_bytes = download_file_bytes(report.storage_key)
    pages = load_image_pages(file_bytes)

    if page_number < 1 or page_number > len(pages):
        raise HTTPException(status_code=404, detail="No such page.")

    buffer = io.BytesIO()
    pages[page_number - 1].save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")
