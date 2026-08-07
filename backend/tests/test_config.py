"""
Tests for OCR_PROVIDER's validation in the config loader - a small
closed set of valid values with a safe default, unlike the plain
present-or-blank secrets in _ENV_SPEC. Calls load_settings() directly
(not the module-level `settings` singleton) so each test can try a
different environment without disturbing every other test's config.
"""

from unittest.mock import patch

import pytest

from app.config import load_settings


def test_rejects_an_unknown_ocr_provider():
    with patch.dict("os.environ", {"OCR_PROVIDER": "not-a-real-provider"}):
        with pytest.raises(RuntimeError, match="OCR_PROVIDER"):
            load_settings()


def test_requires_a_vision_key_when_google_vision_is_selected():
    with patch.dict(
        "os.environ", {"OCR_PROVIDER": "google_vision", "GOOGLE_VISION_API_KEY": ""}
    ):
        with pytest.raises(RuntimeError, match="GOOGLE_VISION_API_KEY"):
            load_settings()


def test_accepts_google_vision_when_a_key_is_present():
    with patch.dict(
        "os.environ",
        {"OCR_PROVIDER": "google_vision", "GOOGLE_VISION_API_KEY": "real-looking-key"},
    ):
        loaded = load_settings()

    assert loaded.ocr_provider == "google_vision"


def test_defaults_to_tesseract_when_ocr_provider_is_blank():
    with patch.dict("os.environ", {"OCR_PROVIDER": ""}):
        loaded = load_settings()

    assert loaded.ocr_provider == "tesseract"


def test_tesseract_never_requires_a_vision_key():
    with patch.dict(
        "os.environ", {"OCR_PROVIDER": "tesseract", "GOOGLE_VISION_API_KEY": ""}
    ):
        loaded = load_settings()

    assert loaded.ocr_provider == "tesseract"
    assert loaded.google_vision_api_key is None
