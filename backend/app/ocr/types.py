"""
The ONE standard OCR result shape. Every provider (Tesseract, Google
Vision, anything added later) must translate its own native response
into exactly this shape - nothing outside this file, and nothing
downstream of OCR, is ever allowed to know a provider's own response
format. That's what makes swapping providers a one-line config change
instead of a rewrite.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    """
    Four corner points, in reading order: top-left, top-right,
    bottom-right, bottom-left. Each point is (x, y) in pixel
    coordinates of the page image OCR actually ran on.

    Four points (not just a rectangle) is what lets this one shape hold
    both Tesseract's axis-aligned rectangles AND Google Vision's
    (possibly skewed/rotated) quadrilaterals without losing
    information either way.
    """

    top_left: tuple[float, float]
    top_right: tuple[float, float]
    bottom_right: tuple[float, float]
    bottom_left: tuple[float, float]

    def to_json(self) -> list[list[float]]:
        """The plain-list-of-points shape stored in the database (JSONB)."""
        return [
            list(self.top_left),
            list(self.top_right),
            list(self.bottom_right),
            list(self.bottom_left),
        ]

    @classmethod
    def from_rectangle(
        cls, left: float, top: float, width: float, height: float
    ) -> "BoundingBox":
        """Builds a BoundingBox from an axis-aligned rectangle (Tesseract's shape)."""
        return cls(
            top_left=(left, top),
            top_right=(left + width, top),
            bottom_right=(left + width, top + height),
            bottom_left=(left, top + height),
        )


@dataclass(frozen=True)
class OcrWord:
    """One word, exactly as OCR read it - the atomic unit of evidence."""

    text: str
    confidence: float  # 0.0-1.0
    bounding_box: BoundingBox
    page_number: int  # 1-indexed


@dataclass(frozen=True)
class OcrResult:
    """
    Everything OCR found in one file (a single image, or every page of
    a PDF), as a flat list of words in reading order. Deliberately no
    separate "full text" field: the words themselves already ARE the
    full text (join their `.text` in order) - storing it twice would
    just be the same truth in two places that could drift apart.
    """

    words: list[OcrWord]


class OcrError(Exception):
    """Base class for OCR provider errors."""


class OcrConfigError(OcrError):
    """Raised when a provider is used without the configuration it needs."""


class OcrProviderError(OcrError):
    """Raised when a provider's underlying engine/API itself reports an error."""
