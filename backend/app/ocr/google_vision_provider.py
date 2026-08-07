"""
The INACTIVE-by-default OCR provider (OCR_PROVIDER=google_vision):
calls the Google Cloud Vision REST API instead of running OCR locally.
Fully implemented and shape-tested now (see test_ocr_google_vision.py),
even though Tesseract is the active provider - switching to this one
later, once billing is enabled, is exactly the one OCR_PROVIDER config
flip plus a real GOOGLE_VISION_API_KEY, nothing else.

Uses DOCUMENT_TEXT_DETECTION (not plain TEXT_DETECTION): it's the
feature that gives per-word confidence scores, which plain
TEXT_DETECTION doesn't. We send one request per page image - Vision's
synchronous REST endpoint only accepts a single image per request, so a
multi-page PDF is rasterized into page images first (the same shared
step Tesseract uses) and each page gets its own request; page numbers
are ours, not Vision's.
"""

import base64
import io

import httpx
from PIL import Image

from app.config import settings
from app.ocr.image_utils import load_image_pages
from app.ocr.provider import OcrProvider
from app.ocr.types import (
    BoundingBox,
    OcrConfigError,
    OcrProviderError,
    OcrResult,
    OcrWord,
)

_VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
_REQUEST_TIMEOUT_SECONDS = 30


class GoogleVisionProvider(OcrProvider):
    def extract(self, file_bytes: bytes) -> OcrResult:
        if not settings.google_vision_api_key:
            raise OcrConfigError(
                "OCR_PROVIDER=google_vision but GOOGLE_VISION_API_KEY is not set. "
                "Add it to backend/.env, or set OCR_PROVIDER=tesseract instead."
            )

        pages = load_image_pages(file_bytes)
        words: list[OcrWord] = []
        for page_number, page_image in enumerate(pages, start=1):
            words.extend(self._extract_page(page_image, page_number))
        return OcrResult(words=words)

    def _extract_page(self, image: Image.Image, page_number: int) -> list[OcrWord]:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        encoded_image = base64.b64encode(buffer.getvalue()).decode("ascii")

        payload = {
            "requests": [
                {
                    "image": {"content": encoded_image},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                }
            ]
        }
        response = httpx.post(
            _VISION_ENDPOINT,
            params={"key": settings.google_vision_api_key},
            json=payload,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response_item = response.json()["responses"][0]

        if "error" in response_item:
            raise OcrProviderError(f"Google Vision error: {response_item['error']}")

        return self._parse_words(response_item, page_number)

    def _parse_words(self, response_item: dict, page_number: int) -> list[OcrWord]:
        full_text_annotation = response_item.get("fullTextAnnotation")
        if not full_text_annotation:
            return []  # No text found on this page - a valid, empty result.

        words = []
        for page in full_text_annotation.get("pages", []):
            for block in page.get("blocks", []):
                for paragraph in block.get("paragraphs", []):
                    for word in paragraph.get("words", []):
                        words.append(self._parse_word(word, page_number))
        return words

    def _parse_word(self, word: dict, page_number: int) -> OcrWord:
        text = "".join(symbol.get("text", "") for symbol in word.get("symbols", []))
        confidence = word.get("confidence", 0.0)
        vertices = word["boundingBox"]["vertices"]
        bounding_box = BoundingBox(
            top_left=self._point(vertices[0]),
            top_right=self._point(vertices[1]),
            bottom_right=self._point(vertices[2]),
            bottom_left=self._point(vertices[3]),
        )
        return OcrWord(
            text=text,
            confidence=confidence,
            bounding_box=bounding_box,
            page_number=page_number,
        )

    @staticmethod
    def _point(vertex: dict) -> tuple[float, float]:
        # Vision omits x/y from the JSON entirely when the value is 0,
        # rather than sending an explicit 0 - so a plain vertex["x"]
        # would KeyError on any word touching the image's top or left
        # edge.
        return (vertex.get("x", 0), vertex.get("y", 0))
