"""
Proves TesseractProvider and GoogleVisionProvider both produce EXACTLY
the same OcrResult/OcrWord shape - the whole reason switching providers
can ever be a one-line config change. If either provider ever drifted
(e.g. returned confidence on a 0-100 scale instead of 0.0-1.0, or a
plain rectangle instead of a BoundingBox), this test catches it here
rather than downstream.

Tesseract runs for real (no network, no API key needed - see
test_worker.py's Task summary note on the system Tesseract binary).
Google Vision's HTTP call is mocked with a realistic
DOCUMENT_TEXT_DETECTION response shape, so this needs no live network
or real API key either.
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image, ImageDraw

from app.config import settings
from app.ocr.google_vision_provider import GoogleVisionProvider
from app.ocr.provider import OcrProvider
from app.ocr.tesseract_provider import TesseractProvider
from app.ocr.types import BoundingBox, OcrResult, OcrWord


def _make_test_png() -> bytes:
    image = Image.new("RGB", (300, 80), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((10, 25), "TEST 123", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _fake_vision_response() -> dict:
    return {
        "responses": [
            {
                "fullTextAnnotation": {
                    "pages": [
                        {
                            "blocks": [
                                {
                                    "paragraphs": [
                                        {
                                            "words": [
                                                {
                                                    "symbols": [
                                                        {"text": "T"},
                                                        {"text": "e"},
                                                        {"text": "s"},
                                                        {"text": "t"},
                                                    ],
                                                    "confidence": 0.93,
                                                    "boundingBox": {
                                                        "vertices": [
                                                            {"x": 10, "y": 25},
                                                            {"x": 40, "y": 25},
                                                            {"x": 40, "y": 40},
                                                            {"x": 10, "y": 40},
                                                        ]
                                                    },
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            }
        ]
    }


def _assert_conforms_to_the_standard_shape(result: OcrResult) -> None:
    assert isinstance(result, OcrResult)
    assert isinstance(result.words, list)
    assert len(result.words) > 0

    for word in result.words:
        assert isinstance(word, OcrWord)
        assert isinstance(word.text, str) and word.text.strip() != ""
        assert isinstance(word.confidence, (int, float))
        assert 0.0 <= word.confidence <= 1.0
        assert isinstance(word.page_number, int)
        assert word.page_number >= 1
        assert isinstance(word.bounding_box, BoundingBox)
        for point in word.bounding_box.to_json():
            assert len(point) == 2
            assert all(isinstance(coordinate, (int, float)) for coordinate in point)


def test_tesseract_provider_is_an_ocr_provider():
    assert isinstance(TesseractProvider(), OcrProvider)


def test_google_vision_provider_is_an_ocr_provider():
    assert isinstance(GoogleVisionProvider(), OcrProvider)


def test_tesseract_provider_output_conforms_to_the_standard_shape():
    result = TesseractProvider().extract(_make_test_png())
    _assert_conforms_to_the_standard_shape(result)


def test_google_vision_provider_output_conforms_to_the_standard_shape():
    # settings is a frozen dataclass - object.__setattr__ is the
    # standard way to patch one field on a frozen instance for a test,
    # restored via the finally block below.
    original_key = settings.google_vision_api_key
    object.__setattr__(settings, "google_vision_api_key", "fake-key-for-tests")

    mock_response = MagicMock()
    mock_response.json.return_value = _fake_vision_response()
    mock_response.raise_for_status.return_value = None

    try:
        with patch("httpx.post", return_value=mock_response):
            result = GoogleVisionProvider().extract(_make_test_png())
    finally:
        object.__setattr__(settings, "google_vision_api_key", original_key)

    _assert_conforms_to_the_standard_shape(result)


def test_both_providers_return_the_exact_same_shared_result_and_word_types():
    # The real drift-prevention check: both providers must build their
    # result from the SAME shared OcrResult/OcrWord classes (not some
    # provider-specific dict or object that merely happens to look
    # similar today) - a provider returning its own ad hoc shape would
    # fail this even if every field name currently matched by accident.
    tesseract_result = TesseractProvider().extract(_make_test_png())

    original_key = settings.google_vision_api_key
    object.__setattr__(settings, "google_vision_api_key", "fake-key-for-tests")
    mock_response = MagicMock()
    mock_response.json.return_value = _fake_vision_response()
    mock_response.raise_for_status.return_value = None
    try:
        with patch("httpx.post", return_value=mock_response):
            vision_result = GoogleVisionProvider().extract(_make_test_png())
    finally:
        object.__setattr__(settings, "google_vision_api_key", original_key)

    assert type(tesseract_result) is type(vision_result) is OcrResult
    assert type(tesseract_result.words[0]) is type(vision_result.words[0]) is OcrWord
    assert (
        type(tesseract_result.words[0].bounding_box)
        is type(vision_result.words[0].bounding_box)
        is BoundingBox
    )


def test_google_vision_provider_refuses_to_run_without_an_api_key():
    from app.ocr.types import OcrConfigError

    original_key = settings.google_vision_api_key
    object.__setattr__(settings, "google_vision_api_key", None)
    try:
        with pytest.raises(OcrConfigError):
            GoogleVisionProvider().extract(_make_test_png())
    finally:
        object.__setattr__(settings, "google_vision_api_key", original_key)
