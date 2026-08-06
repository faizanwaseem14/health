"""
Tests for reading image dimensions. These use REAL images - generated
on the fly with Pillow itself, including a real round-tripped HEIC file
- rather than fake/mocked bytes, since dimension-reading is exactly the
kind of thing that's easy to get subtly wrong with synthetic data.
"""

import io

from PIL import Image

from app.storage.image_metadata import get_image_dimensions


def _make_image_bytes(width: int, height: int, image_format: str) -> bytes:
    image = Image.new("RGB", (width, height), color="blue")
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def test_reads_dimensions_from_a_real_png():
    data = _make_image_bytes(37, 52, "PNG")

    assert get_image_dimensions(data) == (37, 52)


def test_reads_dimensions_from_a_real_jpeg():
    data = _make_image_bytes(100, 64, "JPEG")

    assert get_image_dimensions(data) == (100, 64)


def test_reads_dimensions_from_a_real_heic():
    data = _make_image_bytes(80, 45, "HEIF")

    assert get_image_dimensions(data) == (80, 45)


def test_returns_none_for_a_pdf():
    fake_pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"

    assert get_image_dimensions(fake_pdf_bytes) is None


def test_returns_none_for_garbage_bytes():
    assert get_image_dimensions(b"not an image at all") is None
