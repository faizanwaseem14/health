"""
Tests specific to GoogleVisionProvider's own behavior - request shape,
error handling, and Vision's quirk of omitting zero-valued x/y from
bounding box vertices. General shape-conformance (matching Tesseract's
output shape) is covered in test_ocr_provider_shape.py.

Not the ACTIVE provider (OCR_PROVIDER=tesseract by default), but fully
implemented and tested here with a mocked HTTP call - no live network
or real API key needed.
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.config import settings
from app.ocr.google_vision_provider import GoogleVisionProvider
from app.ocr.types import OcrConfigError, OcrProviderError


def _make_test_png() -> bytes:
    image = Image.new("RGB", (20, 20), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _with_fake_api_key(value: str | None):
    """A tiny context manager for patching the frozen settings object."""

    class _Patch:
        def __enter__(self):
            self.original = settings.google_vision_api_key
            object.__setattr__(settings, "google_vision_api_key", value)
            return settings

        def __exit__(self, *exc_info):
            object.__setattr__(settings, "google_vision_api_key", self.original)

    return _Patch()


def test_raises_config_error_when_api_key_is_blank():
    with _with_fake_api_key(None):
        with pytest.raises(OcrConfigError, match="GOOGLE_VISION_API_KEY"):
            GoogleVisionProvider().extract(_make_test_png())


def test_sends_document_text_detection_with_the_key_as_a_query_param():
    mock_response = MagicMock()
    mock_response.json.return_value = {"responses": [{"fullTextAnnotation": {}}]}
    mock_response.raise_for_status.return_value = None

    with _with_fake_api_key("real-looking-key-123"):
        with patch("httpx.post", return_value=mock_response) as mock_post:
            GoogleVisionProvider().extract(_make_test_png())

    assert mock_post.call_args.kwargs["params"] == {"key": "real-looking-key-123"}
    sent_payload = mock_post.call_args.kwargs["json"]
    feature_type = sent_payload["requests"][0]["features"][0]["type"]
    assert feature_type == "DOCUMENT_TEXT_DETECTION"


def test_returns_no_words_for_a_page_with_no_text_found():
    # A valid, successful response with nothing detected - not an error.
    mock_response = MagicMock()
    mock_response.json.return_value = {"responses": [{}]}
    mock_response.raise_for_status.return_value = None

    with _with_fake_api_key("fake-key"):
        with patch("httpx.post", return_value=mock_response):
            result = GoogleVisionProvider().extract(_make_test_png())

    assert result.words == []


def test_raises_provider_error_when_vision_reports_an_error():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "responses": [{"error": {"code": 3, "message": "Bad image data."}}]
    }
    mock_response.raise_for_status.return_value = None

    with _with_fake_api_key("fake-key"):
        with patch("httpx.post", return_value=mock_response):
            with pytest.raises(OcrProviderError, match="Bad image data"):
                GoogleVisionProvider().extract(_make_test_png())


def test_handles_vertices_missing_zero_valued_x_or_y():
    # Vision omits x/y entirely from a vertex when its value is 0,
    # rather than sending an explicit 0 - a word touching the image's
    # top-left corner would KeyError without defensive handling.
    mock_response = MagicMock()
    mock_response.json.return_value = {
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
                                                    "symbols": [{"text": "A"}],
                                                    "confidence": 0.8,
                                                    "boundingBox": {
                                                        "vertices": [
                                                            {},
                                                            {"x": 5},
                                                            {"x": 5, "y": 5},
                                                            {"y": 5},
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
    mock_response.raise_for_status.return_value = None

    with _with_fake_api_key("fake-key"):
        with patch("httpx.post", return_value=mock_response):
            result = GoogleVisionProvider().extract(_make_test_png())

    assert result.words[0].bounding_box.top_left == (0, 0)
    assert result.words[0].bounding_box.top_right == (5, 0)
    assert result.words[0].bounding_box.bottom_left == (0, 5)
