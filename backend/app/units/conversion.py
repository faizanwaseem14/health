"""
Unit conversion between units that measure the SAME physical quantity,
using fixed, universal conversion factors - metric prefixes and
volume equivalences that are true by definition of the units
themselves. Never a substance-specific factor like a molecular weight,
which would depend on which test this is (e.g. converting a mass
concentration to a molar concentration needs the substance's molar
mass - that's per-test chemistry knowledge, not a unit conversion, and
this module deliberately never does it).

Two units are only ever considered compatible if they're both listed
under the SAME family below. Anything not listed, or a request to
convert between two different families, is refused (returns None) -
never a best-effort or forced conversion.

Supported families, deliberately limited to what's dimensionally exact
regardless of substance:
  - mass concentration (g/dL, mg/dL, g/L, mg/L) - pure metric-prefix
    and per-100mL-vs-per-L arithmetic.
  - cell count concentration (/uL, /mm3, x10^3/uL, x10^9/L, x10^6/uL,
    x10^12/L, ...) - pure metric-prefix arithmetic, plus the fact that
    1 mm^3 and 1 uL are the same volume.
"""

import re

# Each family maps a normalized unit string (see normalize_unit) to its
# factor relative to that family's own base unit. To convert a value
# from unit A to unit B: value_in_base = value * factor[A];
# value_in_B = value_in_base / factor[B].
_MASS_CONCENTRATION_FAMILY: dict[str, float] = {
    "g/dl": 1.0,  # base unit
    "mg/dl": 0.001,  # 1 mg/dL = 0.001 g/dL
    "g/l": 0.1,  # 1 g/L = 0.1 g/dL (1 dL = 0.1 L)
    "mg/l": 0.0001,  # 1 mg/L = 0.0001 g/dL
}

_CELL_COUNT_CONCENTRATION_FAMILY: dict[str, float] = {
    "/ul": 1.0,  # base unit: cells per microliter
    "cells/ul": 1.0,
    "/mm3": 1.0,  # 1 mm^3 == 1 uL - the same volume
    "cells/mm3": 1.0,
    "k/ul": 1_000.0,
    "x10^3/ul": 1_000.0,
    "x10^3/mm3": 1_000.0,
    "x10^9/l": 1_000.0,  # 10^9 per liter == 10^3 per uL
    "x10^6/ul": 1_000_000.0,
    "x10^12/l": 1_000_000.0,  # 10^12 per liter == 10^6 per uL
}

_UNIT_FAMILIES: list[dict[str, float]] = [
    _MASS_CONCENTRATION_FAMILY,
    _CELL_COUNT_CONCENTRATION_FAMILY,
]


def normalize_unit(unit: str) -> str:
    """Lowercased, no internal whitespace - so "g/dL", "g / dL", and
    "G/DL" all match the same catalog key. Purely a formatting
    normalization, never a decision about what the unit means."""
    return re.sub(r"\s+", "", unit).lower()


def _find_family(unit: str) -> dict[str, float] | None:
    normalized = normalize_unit(unit)
    for family in _UNIT_FAMILIES:
        if normalized in family:
            return family
    return None


def units_are_compatible(unit_a: str, unit_b: str) -> bool:
    """True only if both units are known AND belong to the same family
    - i.e. a real, well-defined conversion factor exists between them."""
    family_a = _find_family(unit_a)
    family_b = _find_family(unit_b)
    return family_a is not None and family_a is family_b


def convert_value(value: float, from_unit: str, to_unit: str) -> float | None:
    """
    Converts `value` from from_unit to to_unit, ONLY if both units
    belong to the same known family. Returns None - never a guess,
    never a forced conversion - if either unit is unrecognized or the
    two units belong to different (incompatible) families.
    """
    if not units_are_compatible(from_unit, to_unit):
        return None

    family = _find_family(from_unit)
    value_in_base = value * family[normalize_unit(from_unit)]
    return value_in_base / family[normalize_unit(to_unit)]
