"""
Tests for real, byte-level file type and size validation. No database
or R2 needed - these are pure functions operating on bytes.
"""

import asyncio
import io

import pytest
from starlette.datastructures import UploadFile

from app.storage.file_validation import (
    MAX_UPLOAD_SIZE_BYTES,
    FileTooLargeError,
    InvalidFileTypeError,
    detect_real_mime_type,
    read_upload_within_size_limit,
    validate_file_type,
)

# Real signature bytes for each format, taken from the actual file
# specs (and, for HEIC, confirmed by round-tripping a real HEIC file
# through Pillow while building this - see the router's summary).
_REAL_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 20
_REAL_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
_REAL_PDF_BYTES = b"%PDF-1.4\n" + b"\x00" * 20
_REAL_HEIC_BYTES = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00" + b"\x00" * 20


def test_detects_real_jpeg():
    assert detect_real_mime_type(_REAL_JPEG_BYTES) == "image/jpeg"


def test_detects_real_png():
    assert detect_real_mime_type(_REAL_PNG_BYTES) == "image/png"


def test_detects_real_pdf():
    assert detect_real_mime_type(_REAL_PDF_BYTES) == "application/pdf"


def test_detects_real_heic():
    assert detect_real_mime_type(_REAL_HEIC_BYTES) == "image/heic"


def test_rejects_plain_text_pretending_to_be_a_photo():
    # The actual attack this whole module exists to stop: a file that
    # is NOT an image, dressed up with a misleading name/extension.
    # detect_real_mime_type only ever looks at the bytes, so faking the
    # filename does nothing here - there's no filename parameter at all.
    fake_bytes = b"just some plain text pretending to be a photo"

    assert detect_real_mime_type(fake_bytes) is None


def test_rejects_empty_file():
    assert detect_real_mime_type(b"") is None


def test_validate_file_type_raises_for_unrecognized_bytes():
    with pytest.raises(InvalidFileTypeError):
        validate_file_type(b"not a real file")


def test_validate_file_type_returns_mime_type_for_a_real_file():
    assert validate_file_type(_REAL_PNG_BYTES) == "image/png"


def _make_upload_file(data: bytes) -> UploadFile:
    return UploadFile(filename="test.jpg", file=io.BytesIO(data))


def test_read_upload_within_size_limit_accepts_a_small_file():
    upload = _make_upload_file(_REAL_JPEG_BYTES)

    result = asyncio.run(read_upload_within_size_limit(upload))

    assert result == _REAL_JPEG_BYTES


def test_read_upload_within_size_limit_rejects_an_oversized_file():
    oversized = b"\xff\xd8\xff" + (b"0" * (MAX_UPLOAD_SIZE_BYTES + 1))
    upload = _make_upload_file(oversized)

    with pytest.raises(FileTooLargeError):
        asyncio.run(read_upload_within_size_limit(upload))


def test_read_upload_within_size_limit_accepts_exactly_the_limit():
    exactly_at_limit = b"0" * MAX_UPLOAD_SIZE_BYTES
    upload = _make_upload_file(exactly_at_limit)

    result = asyncio.run(read_upload_within_size_limit(upload))

    assert len(result) == MAX_UPLOAD_SIZE_BYTES
