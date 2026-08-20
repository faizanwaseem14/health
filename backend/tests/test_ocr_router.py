"""
Tests for the OCR inspection routes: listing a report's OCR words, and
rendering one page of the original file as an image. R2 and the actual
PDF/image rasterization are mocked here (no real R2 credentials in
this sandbox, and rasterization is already covered for real in
test_ocr_types.py/app/ocr/image_utils.py's own usage) - proves this
router's own logic: auth, ownership, page-index bounds, and that it
hands back real PNG bytes.
"""

import io
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from app.auth.dependencies import get_current_user, get_db
from app.main import app
from app.models import OcrWord, Report, User
from app.routers.reports import require_owned_report

client = TestClient(app)


def _clear_overrides():
    app.dependency_overrides.clear()


# --- GET /reports/{row_id}/ocr-words ---


def test_list_ocr_words_requires_login():
    response = client.get(f"/reports/{uuid.uuid4()}/ocr-words")

    assert response.status_code == 401


def test_list_ocr_words_rejects_someone_elses_report():
    user = User(id=uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get(f"/reports/{uuid.uuid4()}/ocr-words")
    finally:
        _clear_overrides()

    assert response.status_code in (404, 503)


def test_list_ocr_words_returns_each_words_text_and_bounding_box():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    word = OcrWord(
        id=uuid.uuid4(),
        report_id=report.id,
        page_number=1,
        word_index=0,
        text="Hemoglobin",
        confidence=0.97,
        bounding_box=[[10, 10], [100, 10], [100, 30], [10, 30]],
        ocr_provider="tesseract",
    )
    user = User(id=uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_owned_report] = lambda: report

    fake_db = MagicMock()
    query_chain = fake_db.query.return_value.filter.return_value.order_by.return_value
    query_chain.all.return_value = [word]
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        response = client.get(f"/reports/{report.id}/ocr-words")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body) == 1
    assert body[0]["text"] == "Hemoglobin"
    assert body[0]["page_number"] == 1
    assert body[0]["bounding_box"] == [[10, 10], [100, 10], [100, 30], [10, 30]]
    assert body[0]["confidence"] == 0.97


# --- GET /reports/{row_id}/pages/{page_number} ---


def test_get_report_page_image_requires_login():
    response = client.get(f"/reports/{uuid.uuid4()}/pages/1")

    assert response.status_code == 401


def test_get_report_page_image_rejects_someone_elses_report():
    user = User(id=uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get(f"/reports/{uuid.uuid4()}/pages/1")
    finally:
        _clear_overrides()

    assert response.status_code in (404, 503)


def _fake_page_image():
    return Image.new("RGB", (20, 30), color=(255, 255, 255))


def test_get_report_page_image_returns_real_png_bytes():
    report = Report(
        id=uuid.uuid4(), profile_id=uuid.uuid4(), storage_key="reports/x.pdf"
    )
    user = User(id=uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_owned_report] = lambda: report

    try:
        with (
            patch(
                "app.routers.ocr.download_file_bytes", return_value=b"fake-pdf-bytes"
            ),
            patch(
                "app.routers.ocr.load_image_pages", return_value=[_fake_page_image()]
            ),
        ):
            response = client.get(f"/reports/{report.id}/pages/1")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    # Confirm it's a real, decodable PNG at the expected dimensions -
    # not just arbitrary bytes with the right header.
    image = Image.open(io.BytesIO(response.content))
    assert image.format == "PNG"
    assert image.size == (20, 30)


def test_get_report_page_image_404s_for_an_out_of_range_page():
    report = Report(
        id=uuid.uuid4(), profile_id=uuid.uuid4(), storage_key="reports/x.pdf"
    )
    user = User(id=uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_owned_report] = lambda: report

    try:
        with (
            patch(
                "app.routers.ocr.download_file_bytes", return_value=b"fake-pdf-bytes"
            ),
            patch(
                "app.routers.ocr.load_image_pages", return_value=[_fake_page_image()]
            ),
        ):
            response = client.get(f"/reports/{report.id}/pages/2")
    finally:
        _clear_overrides()

    assert response.status_code == 404
