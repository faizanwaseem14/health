"""
Turns any file bytes we accept at upload time (JPEG/PNG/HEIC/PDF) into a
list of Pillow images, one per page - shared by every OCR provider so
"how do we read a PDF's pages" and "how do we open a HEIC photo" is
solved exactly once, instead of once per provider.
"""

import io

import pymupdf
from PIL import Image

# Importing this registers HEIC/HEIF support with Pillow, as a side
# effect - the exact same registration the upload endpoint's
# dimension-reading code already relies on. Safe to import here too:
# the registration itself is idempotent.
import app.storage.image_metadata  # noqa: E402, F401
from app.storage.file_validation import detect_real_mime_type

# Pages are rasterized at this resolution before OCR. 300 DPI is the
# standard "good enough for OCR" resolution - much lower and small
# print gets blurry; much higher just slows OCR down for no accuracy
# gain. PDFs default to 72 DPI (screen resolution), so we scale up.
_PDF_RENDER_DPI = 300
_PDF_ZOOM_FACTOR = _PDF_RENDER_DPI / 72


def load_image_pages(file_bytes: bytes) -> list[Image.Image]:
    """
    Returns one Pillow image per page: a single-element list for a
    photo (JPEG/PNG/HEIC), or one element per page for a PDF.
    """
    mime_type = detect_real_mime_type(file_bytes)

    if mime_type == "application/pdf":
        return _rasterize_pdf_pages(file_bytes)

    # Anything else we accept at upload time (JPEG/PNG/HEIC) is already
    # a single image Pillow can open directly.
    return [Image.open(io.BytesIO(file_bytes)).convert("RGB")]


def _rasterize_pdf_pages(pdf_bytes: bytes) -> list[Image.Image]:
    matrix = pymupdf.Matrix(_PDF_ZOOM_FACTOR, _PDF_ZOOM_FACTOR)
    pages = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        for pdf_page in document:
            pixmap = pdf_page.get_pixmap(matrix=matrix)
            image = Image.frombytes(
                "RGB", (pixmap.width, pixmap.height), pixmap.samples
            )
            pages.append(image)
    return pages
