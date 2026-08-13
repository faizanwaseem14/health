"""
Applies unit conversion to a report's results: for every result whose
test has been resolved to a catalog entry (app/test_names/) with a
known default_unit, computes a DERIVED value in that unit - stored
separately in converted_value_numeric/converted_unit, never touching
the original printed value/unit.

Nothing here invents a target unit: the target is always the catalog's
own default_unit (never a hardcoded per-test unit choice in this
file), and the conversion itself only ever happens when
app.units.conversion confirms the two units are genuinely compatible.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Result, TestAlias
from app.trust.numeric import parse_comparator_and_number
from app.units.conversion import convert_value, normalize_unit


def apply_unit_conversion_for_report(db: Session, report_id: UUID) -> None:
    """
    For every result in the report:
      - clears any previously-derived converted_value_numeric/
        converted_unit first (same replace-on-retry posture as the
        rest of the pipeline)
      - then, ONLY when the result has a resolved test_alias_id whose
        catalog entry specifies a default_unit, the result has its own
        printed unit, and that unit is genuinely convertible to the
        default unit, stores the derived value/unit

    Every other case (no resolved alias, no default_unit on the alias,
    no printed unit, the printed unit already matches the default, an
    unparseable value, or units that aren't in the same conversion
    family) leaves converted_value_numeric/converted_unit as None -
    never a guess, never a forced conversion.
    """
    results = db.query(Result).filter(Result.report_id == report_id).all()
    if not results:
        return

    alias_ids = {result.test_alias_id for result in results if result.test_alias_id}
    aliases_by_id = (
        {
            alias.id: alias
            for alias in db.query(TestAlias).filter(TestAlias.id.in_(alias_ids)).all()
        }
        if alias_ids
        else {}
    )

    for result in results:
        result.converted_value_numeric = None
        result.converted_unit = None

        alias = aliases_by_id.get(result.test_alias_id)
        if alias is None or not alias.default_unit or not result.unit:
            continue
        if normalize_unit(result.unit) == normalize_unit(alias.default_unit):
            continue  # already in the default unit - nothing to derive

        parsed_value = parse_comparator_and_number(result.value)
        if parsed_value is None:
            continue
        _, number = parsed_value

        converted = convert_value(number, result.unit, alias.default_unit)
        if converted is None:
            continue  # not a known, compatible conversion - never force it

        result.converted_value_numeric = converted
        result.converted_unit = alias.default_unit

    db.commit()
