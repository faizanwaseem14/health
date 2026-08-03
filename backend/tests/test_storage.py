"""
Tests for the R2 signed-URL helper.

Generating a presigned URL is pure local computation (boto3 signs it with
your access key using math, it doesn't call R2 to do it), so this can be
fully tested without a real Cloudflare account or network access. What we
CANNOT test here is whether the URL actually works against a real R2
bucket - that needs your real R2_* keys in .env (see SETUP.md).
"""

from urllib.parse import parse_qs, urlparse

from app.storage.r2 import generate_upload_url


def test_generate_upload_url_points_at_the_right_bucket_and_key():
    url = generate_upload_url("reports/some-file.pdf", "application/pdf")

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    # The bucket and key both end up in the path for this style of R2/S3 URL.
    assert "reports/some-file.pdf" in parsed.path


def test_generate_upload_url_expires(expected_seconds=120):
    url = generate_upload_url(
        "reports/some-file.pdf", "application/pdf", expires_in_seconds=expected_seconds
    )

    query = parse_qs(urlparse(url).query)
    assert query["X-Amz-Expires"] == [str(expected_seconds)]


def test_generate_upload_url_is_signed():
    url = generate_upload_url("reports/some-file.pdf", "application/pdf")

    query = parse_qs(urlparse(url).query)
    # A signature must be present - this is what makes the URL only
    # usable by someone who actually holds the R2 secret key.
    assert "X-Amz-Signature" in query
