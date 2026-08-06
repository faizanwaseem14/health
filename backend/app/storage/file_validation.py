"""
Server-side validation for uploaded report files.

The whole point of this file: NEVER trust what the client claims about
a file (its filename extension, or the Content-Type header the browser
sent). Both of those are just labels the client attached and can be
wrong - or deliberately faked. The only thing we trust is the file's
own bytes.

We accept exactly four formats: JPEG, PNG, HEIC, and PDF. Every real
file in one of those formats starts with a fixed, well-known sequence
of bytes ("magic numbers") - that's how every OS and image viewer
identifies a file too. We check those bytes ourselves.
"""

from fastapi import UploadFile

# 10 MB, in bytes. Named here once instead of a raw number scattered
# through the code.
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024

_JPEG_SIGNATURE = b"\xff\xd8\xff"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PDF_SIGNATURE = b"%PDF-"

# HEIC/HEIF files are an "ISO Base Media File Format" container (the
# same family as MP4). Bytes 4-7 always spell "ftyp", followed by a
# 4-byte "major brand" code that says which flavor it is. These are the
# brand codes real HEIC/HEIF photos use - confirmed by round-tripping an
# actual HEIC file through Pillow while building this (see the Task
# summary): a real iPhone-style HEIC photo's bytes look like
# b"...ftypheic...".
_HEIC_BRAND_CODES = {
    b"heic",
    b"heix",
    b"heim",
    b"heis",
    b"hevc",
    b"hevx",
    b"hevm",
    b"hevs",
    b"mif1",
    b"msf1",
}

# What we save the file as in R2, based on the REAL type we detected -
# never based on whatever the client's filename claimed.
EXTENSION_BY_MIME_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/heic": ".heic",
    "application/pdf": ".pdf",
}


class FileTooLargeError(Exception):
    """Raised when a file is larger than MAX_UPLOAD_SIZE_BYTES."""


class InvalidFileTypeError(Exception):
    """Raised when a file's actual bytes don't match an allowed type."""


def detect_real_mime_type(file_bytes: bytes) -> str | None:
    """
    Looks at the file's own bytes and returns the real MIME type if it's
    one we accept, or None if it isn't recognized as any of them - no
    matter what the filename or Content-Type header claimed.
    """
    if file_bytes.startswith(_JPEG_SIGNATURE):
        return "image/jpeg"
    if file_bytes.startswith(_PNG_SIGNATURE):
        return "image/png"
    if file_bytes.startswith(_PDF_SIGNATURE):
        return "application/pdf"
    if (
        len(file_bytes) >= 12
        and file_bytes[4:8] == b"ftyp"
        and file_bytes[8:12] in _HEIC_BRAND_CODES
    ):
        return "image/heic"
    return None


def validate_file_type(file_bytes: bytes) -> str:
    """
    Same as detect_real_mime_type(), but raises InvalidFileTypeError
    instead of returning None - for when "not a valid type" should stop
    the request rather than be handled by the caller.
    """
    mime_type = detect_real_mime_type(file_bytes)
    if mime_type is None:
        raise InvalidFileTypeError("File is not a valid JPEG, PNG, HEIC, or PDF.")
    return mime_type


async def read_upload_within_size_limit(file: UploadFile) -> bytes:
    """
    Reads an uploaded file's bytes, stopping the moment it's clear the
    file is too big - rather than reading the whole thing into memory
    first and checking afterward. That matters: without this, someone
    could send a multi-gigabyte file and we'd buffer all of it before
    ever rejecting it.
    """
    chunk_size = 1024 * 1024  # 1 MB at a time
    chunks: list[bytes] = []
    total_size = 0

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > MAX_UPLOAD_SIZE_BYTES:
            raise FileTooLargeError(
                f"File is larger than the "
                f"{MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB limit."
            )
        chunks.append(chunk)

    return b"".join(chunks)
