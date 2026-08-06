"""
Reads an image's width/height straight from its raw bytes.

Pillow only needs to read the file's header to get its dimensions - it
doesn't decode the whole image - so this is fast and safe to run on
every upload.
"""

import io

from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener

# Teaches Pillow how to open HEIC/HEIF files. Without this, Image.open()
# only understands the formats built into Pillow itself (JPEG, PNG,
# ...) - HEIC needs this extra registration once, when the app starts.
register_heif_opener()


def get_image_dimensions(file_bytes: bytes) -> tuple[int, int] | None:
    """
    Returns (width, height) for a JPEG/PNG/HEIC image, or None if the
    bytes aren't an image format Pillow can open - e.g. a PDF has no
    "image dimensions" the way a photo does.
    """
    try:
        with Image.open(io.BytesIO(file_bytes)) as image:
            return image.size
    except (UnidentifiedImageError, OSError):
        return None
