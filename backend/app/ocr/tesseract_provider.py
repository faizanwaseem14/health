"""
The ACTIVE OCR provider (OCR_PROVIDER=tesseract, the default): runs
Tesseract, a free, open-source OCR engine that runs entirely on this
machine - no API key, no billing, no network call. Needs the Tesseract
program itself installed separately (see SETUP.md); pytesseract here is
just a thin Python wrapper that shells out to it.
"""

import pytesseract
from PIL import Image

from app.ocr.image_utils import load_image_pages
from app.ocr.provider import OcrProvider
from app.ocr.types import BoundingBox, OcrResult, OcrWord

# Tesseract marks non-word rows (page/block/paragraph/line-level
# aggregate rows) in image_to_data's output with a confidence of -1 -
# those aren't actual words and must be skipped, not stored as evidence
# with a nonsense confidence value.
_NON_WORD_CONFIDENCE = -1


class TesseractProvider(OcrProvider):
    def extract(self, file_bytes: bytes) -> OcrResult:
        pages = load_image_pages(file_bytes)
        words: list[OcrWord] = []
        for page_number, page_image in enumerate(pages, start=1):
            words.extend(self._extract_page(page_image, page_number))
        return OcrResult(words=words)

    def _extract_page(self, image: Image.Image, page_number: int) -> list[OcrWord]:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

        words = []
        for index, text in enumerate(data["text"]):
            confidence = int(data["conf"][index])
            if confidence == _NON_WORD_CONFIDENCE or not text.strip():
                continue

            bounding_box = BoundingBox.from_rectangle(
                left=data["left"][index],
                top=data["top"][index],
                width=data["width"][index],
                height=data["height"][index],
            )
            words.append(
                OcrWord(
                    text=text,
                    confidence=confidence / 100,
                    bounding_box=bounding_box,
                    page_number=page_number,
                )
            )
        return words
