"""
The abstract OCR provider interface. Every OCR engine we support
implements exactly this one method - nothing else about a provider is
ever called from outside this package. That's the whole point: the
worker, the evidence-storage code, and everything else in the app only
ever talk to an OcrProvider, never to "Tesseract" or "Google Vision"
directly.
"""

from abc import ABC, abstractmethod

from app.ocr.types import OcrResult


class OcrProvider(ABC):
    @abstractmethod
    def extract(self, file_bytes: bytes) -> OcrResult:
        """
        Runs OCR on one uploaded file's raw bytes (JPEG/PNG/HEIC, or a
        multi-page PDF) and returns the standard OcrResult shape.

        Implementations detect the real file type themselves (the same
        magic-byte sniffing used at upload time - never trust a
        filename or header) and handle PDFs by processing every page.
        """
