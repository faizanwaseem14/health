"""
The extraction prompt and its version. EXTRACTION_PROMPT_VERSION must
be bumped any time the prompt text changes in a way that could change
what gets extracted - it's recorded on every processed report (see
app/ai/service.py) so we always know which prompt produced which
results.

EXTRACTION_MODEL is a cheap model - this is plain structured extraction
from text Claude already has in front of it (no deep reasoning needed),
so a small, fast model keeps per-report cost low.
"""

from app.models import OcrWord

EXTRACTION_MODEL = "claude-haiku-4-5"
EXTRACTION_PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """
You are given the OCR text of a medical lab report, as a numbered list
of words in reading order. Each word is tagged with the page it came
from.

Your ONLY job: find every individual test result printed on the report,
and record it in structured form. You are doing extraction, not
interpretation - never explain what a result means, never give medical
advice, and never guess a value the report doesn't actually print.

For each test result row, record:
- raw_test_name: the test name exactly as printed (e.g. "HGB", "Total Chol.")
- canonical_test_name: your best standard/common name for that same
  test (e.g. "Hemoglobin", "Total Cholesterol")
- value: the result exactly as printed, as text (e.g. "13.5", "Negative", "<0.1")
- unit: the unit exactly as printed, or null if none is printed
- reference_range: the reference/normal range exactly as printed
  (e.g. "12.0-15.5", "Negative"), or null if none is printed. Never
  invent, calculate, or look up a reference range - only use what the
  report itself prints next to this result.
- date: the date printed for this result, exactly as printed, or null
  if none is visible near it
- lab: the lab or facility name printed on the report, or null if none
  is visible
- evidence_word_indices: the numbers (from the numbered word list
  above) of every word that supports this row - the test name, the
  value, the unit, and the reference range, wherever they appear
- confidence: your own confidence (0.0-1.0) that you read this exact
  row correctly

Rules:
- Only extract rows that are genuinely lab test results. Headers,
  patient demographics, and page furniture are not test rows.
- If the same test appears more than once, record it as separate rows.
- If you cannot find any test rows, return an empty list - never invent one.
""".strip()


def build_word_list_prompt(ocr_words: list[OcrWord]) -> str:
    """
    Renders a report's stored OCR words as the numbered list the system
    prompt refers to. The order here IS the index Claude cites back in
    evidence_word_indices, so callers must pass words already ordered
    by (page_number, word_index) - the same order app.ocr.evidence
    stores them in.
    """
    lines = [
        f"[{index}] (page {word.page_number}) {word.text}"
        for index, word in enumerate(ocr_words)
    ]
    return "\n".join(lines)
