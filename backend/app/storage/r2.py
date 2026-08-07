"""
Handles talking to Cloudflare R2 (our private file storage) for report
uploads.

R2 is "S3-compatible", meaning it understands the same API Amazon S3
does - so we can use boto3 (AWS's official Python library) to talk to
it, just pointed at Cloudflare's endpoint instead of Amazon's.

This file has two ways of getting a file into R2:

  generate_upload_url() hands back a short-lived "signed URL" - a link
  that would let the FRONTEND upload directly to R2 itself, without the
  file passing through our backend at all. Not used yet (Day 1 built it
  ahead of time; nothing calls it yet).

  upload_file_bytes() uploads bytes we already have on the backend
  directly to R2, using our own credentials. This is what the Day 2
  upload endpoint uses: we need the file's actual bytes in hand anyway,
  to check its real type and compute its checksum, so it makes sense to
  push it to R2 ourselves once that's done, rather than route back
  through a signed URL.

Either way, the bucket itself has no public access configured at all -
these are the only two ways in.
"""

import boto3

from app.config import settings

# One shared client, built once when this module is first imported.
# region_name="auto" is what Cloudflare's docs recommend for R2 - R2
# doesn't have AWS-style regions, but boto3 requires *some* value here.
_r2_client = boto3.client(
    "s3",
    endpoint_url=settings.r2_endpoint_url,
    aws_access_key_id=settings.r2_access_key_id,
    aws_secret_access_key=settings.r2_secret_access_key,
    region_name="auto",
)


def generate_upload_url(
    storage_key: str, content_type: str, expires_in_seconds: int = 300
) -> str:
    """
    Returns a temporary, private URL that can be used to upload ONE file
    directly to R2, valid for `expires_in_seconds` (default: 5 minutes).

    Arguments:
      storage_key: the path/filename to save the file under inside the
        bucket, e.g. "reports/<uuid>.pdf". The caller decides this -
        it isn't generated here.
      content_type: the MIME type the upload must match, e.g.
        "application/pdf". R2 will reject an upload that doesn't match.
      expires_in_seconds: how long the link stays valid for.

    This does NOT make the file - or the bucket - public. This URL is
    the only way to write to that one exact key, and only until it
    expires.
    """
    return _r2_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": storage_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in_seconds,
    )


def upload_file_bytes(storage_key: str, file_bytes: bytes, content_type: str) -> None:
    """
    Uploads bytes we already have directly to R2, through our own
    backend credentials - as opposed to generate_upload_url(), which is
    for letting someone ELSE upload without the file ever reaching us.

    Whatever bytes are passed in are stored EXACTLY as given - nothing
    here compresses, resizes, or otherwise touches the file. Preserving
    the untouched original is the whole point of this function.
    """
    _r2_client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=storage_key,
        Body=file_bytes,
        ContentType=content_type,
    )


def download_file_bytes(storage_key: str) -> bytes:
    """
    Downloads a file's bytes back out of R2 by its storage key - the
    read-side counterpart to upload_file_bytes(). Used by the OCR
    worker to fetch a report's original file for processing; nothing
    here modifies the stored object.
    """
    response = _r2_client.get_object(Bucket=settings.r2_bucket_name, Key=storage_key)
    return response["Body"].read()
