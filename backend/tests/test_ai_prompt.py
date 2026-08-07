"""
Tests for building the numbered OCR word list Claude sees - the index
positions here are exactly what evidence_word_indices refers back to,
so getting the numbering right matters.
"""

import uuid

from app.ai.prompt import build_word_list_prompt
from app.models import OcrWord


def _word(text: str, page_number: int) -> OcrWord:
    return OcrWord(
        id=uuid.uuid4(),
        report_id=uuid.uuid4(),
        page_number=page_number,
        word_index=0,
        text=text,
        confidence=0.9,
        bounding_box=[[0, 0], [1, 0], [1, 1], [0, 1]],
        ocr_provider="tesseract",
    )


def test_words_are_numbered_from_zero_in_order():
    words = [_word("Hemoglobin", 1), _word("13.5", 1), _word("g/dL", 1)]

    prompt = build_word_list_prompt(words)

    lines = prompt.splitlines()
    assert lines[0] == "[0] (page 1) Hemoglobin"
    assert lines[1] == "[1] (page 1) 13.5"
    assert lines[2] == "[2] (page 1) g/dL"


def test_page_number_is_included_per_word():
    words = [_word("Page1Word", 1), _word("Page2Word", 2)]

    prompt = build_word_list_prompt(words)

    assert "(page 1) Page1Word" in prompt
    assert "(page 2) Page2Word" in prompt


def test_empty_word_list_produces_an_empty_prompt():
    assert build_word_list_prompt([]) == ""
