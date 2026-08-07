"""
OCR: turns a report's raw file bytes into text, with a per-word
confidence score, bounding box, and page number - the "evidence" a
later day's AI extraction (and, further out, a human reviewer) will
build on.

Everything downstream of OCR depends ONLY on the standard shapes in
`app.ocr.types` (OcrResult / OcrWord) - never on which engine produced
them. `app.ocr.provider.OcrProvider` is the one interface every engine
implements; `app.ocr.service.get_active_provider()` is the one place
that decides, from config, which engine is actually running.
"""
