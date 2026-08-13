"""
Tests for the pure unit-conversion math (app/units/conversion.py).
"""

from app.units.conversion import convert_value, normalize_unit, units_are_compatible

# --- normalize_unit ---


def test_normalize_unit_collapses_case_and_whitespace():
    assert normalize_unit("g/dL") == normalize_unit(" G / DL ")


# --- units_are_compatible ---


def test_units_in_the_same_mass_concentration_family_are_compatible():
    assert units_are_compatible("mg/dL", "g/dL") is True


def test_units_in_the_same_cell_count_family_are_compatible():
    assert units_are_compatible("x10^9/L", "x10^3/uL") is True


def test_units_in_different_families_are_not_compatible():
    assert units_are_compatible("g/dL", "x10^9/L") is False


def test_an_unrecognized_unit_is_never_compatible_with_anything():
    assert units_are_compatible("g/dL", "furlongs") is False
    assert units_are_compatible("furlongs", "g/dL") is False


# --- convert_value: mass concentration ---


def test_converts_mg_per_dl_to_g_per_dl():
    # 1000 mg/dL == 1 g/dL
    assert convert_value(1000.0, "mg/dL", "g/dL") == 1.0


def test_converts_g_per_l_to_g_per_dl():
    # 10 g/L == 1 g/dL
    assert convert_value(10.0, "g/L", "g/dL") == 1.0


def test_round_trips_through_two_mass_units():
    original = 13.5
    converted = convert_value(original, "g/dL", "mg/dL")
    back = convert_value(converted, "mg/dL", "g/dL")
    assert round(back, 6) == original


# --- convert_value: cell count concentration ---


def test_converts_x10_9_per_l_to_x10_3_per_ul():
    # 1 x10^9/L WBC count == 1 x10^3/uL (a very common WBC unit pair)
    assert convert_value(1.0, "x10^9/L", "x10^3/uL") == 1.0


def test_mm3_and_ul_are_the_same_volume():
    assert convert_value(7500.0, "/mm3", "/uL") == 7500.0


# --- convert_value: refusals ---


def test_returns_none_for_incompatible_families():
    assert convert_value(13.5, "g/dL", "x10^9/L") is None


def test_returns_none_for_an_unrecognized_unit():
    assert convert_value(13.5, "g/dL", "furlongs") is None
    assert convert_value(13.5, "furlongs", "g/dL") is None
