"""
AI extraction: turns a report's stored OCR evidence (app.ocr) into
structured test-result rows using Claude.

This is ONLY structured extraction - reading what the report already
prints into a strict shape. It never computes a flag, gives medical
advice, or invents a value the report doesn't print. Verifying
extracted values against their OCR evidence (the "trust chain") is
explicitly a later day's work, not this package's job.
"""
