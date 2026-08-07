"""
Tests for the standard OCR result shapes themselves - the small amount
of real logic here (BoundingBox's two constructors) is worth testing
directly, independent of any provider.
"""

from app.ocr.types import BoundingBox, OcrResult, OcrWord


def test_bounding_box_from_rectangle_builds_four_correct_corners():
    box = BoundingBox.from_rectangle(left=10, top=20, width=30, height=5)

    assert box.top_left == (10, 20)
    assert box.top_right == (40, 20)
    assert box.bottom_right == (40, 25)
    assert box.bottom_left == (10, 25)


def test_bounding_box_to_json_is_four_points_in_reading_order():
    box = BoundingBox(
        top_left=(1, 2), top_right=(3, 2), bottom_right=(3, 4), bottom_left=(1, 4)
    )

    assert box.to_json() == [[1, 2], [3, 2], [3, 4], [1, 4]]


def test_ocr_result_holds_words_in_order():
    box = BoundingBox.from_rectangle(0, 0, 1, 1)
    words = [
        OcrWord(text="Hello", confidence=0.9, bounding_box=box, page_number=1),
        OcrWord(text="World", confidence=0.8, bounding_box=box, page_number=1),
    ]

    result = OcrResult(words=words)

    assert [word.text for word in result.words] == ["Hello", "World"]
