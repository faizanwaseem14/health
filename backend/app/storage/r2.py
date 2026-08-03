"""
Handles talking to Cloudflare R2 (our private file storage) for report
uploads.

R2 is "S3-compatible", meaning it understands the same API Amazon S3
does - so we can use boto3 (AWS's official Python library) to talk to
it, just pointed at Cloudflare's endpoint instead of Amazon's.

Nothing in this file uploads a file itself. Instead, `generate_upload_url`
hands back a short-lived "signed URL" - a temporary, one-time-use link
that will later let the FRONTEND upload a file directly to R2, without
the file ever passing through our backend server. The bucket itself has
no public access configured at all; a signed URL like this is the only
way in, and only until it expires.

We are NOT building the upload UI yet (that's a later day) - this file
is just the helper that will generate those links when we do.
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
