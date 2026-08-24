"""
Computes how a test's value has changed over time across every report
in a profile - the data behind the trends screen.

Deliberately conservative about what counts as "the same test, safe to
compare": grouping is by `Result.test_alias_id` (the deterministic
catalog match - see app/test_names/), never by the AI's own free-text
`canonical_test_name` guess, and a value is only ever plotted alongside
another if they're either already in the same unit or convertible
between units with a real, well-defined factor (app/units/conversion.py
- never a forced or best-effort conversion). A result that fails either
of those isn't silently dropped - it comes back in `excluded_points`
with a reason, so the caller can say so rather than just showing a
suspiciously short chart.

This module computes numbers only. It never writes a sentence about
what a trend means - that's the frontend's job, from a fixed template
keyed off `flag`, same "deterministic, no AI" rule as the status badges
themselves.
"""

from sqlalchemy.orm import Session

from app.models import Report, Result, TestAlias
from app.units.conversion import convert_value, normalize_unit


def _pick_chart_unit(alias: TestAlias, rows: list[tuple[Result, Report]]) -> str | None:
    """
    The one unit every point in this test's chart gets expressed in.
    Prefers the test catalog's own standard unit; falls back to
    whatever unit the most recent report printed, so a test with no
    catalog default_unit still gets a consistent, real (not invented)
    unit to plot against.
    """
    if alias.default_unit:
        return alias.default_unit
    for result, _report in reversed(rows):
        if result.unit:
            return result.unit
    return None


def _comparable_value(
    value: float, raw_unit: str | None, chart_unit: str | None
) -> float | None:
    """
    Returns `value` expressed in `chart_unit`, or None if that can't be
    done safely. Two unitless numbers are treated as directly
    comparable; a unitless number next to a unit-bearing one is not
    (there's no way to know they measure the same thing the same way).
    """
    if raw_unit is None and chart_unit is None:
        return value
    if raw_unit is None or chart_unit is None:
        return None
    if normalize_unit(raw_unit) == normalize_unit(chart_unit):
        return value
    return convert_value(value, raw_unit, chart_unit)


def compute_report_trends(db: Session, report: Report) -> list[dict]:
    """
    Returns one entry per trend-eligible test found in `report` (i.e.
    resolved to a catalog test_alias_id - an unresolved raw test name
    can't be safely grouped with anything from another report, so it
    simply doesn't get a trend), each with every comparable point for
    that test across EVERY report in the same profile, ordered by
    report upload time.

    Order matches the anchor report's own results (so trend "chips" on
    the frontend line up with the order results appear on that
    report's own results screen).
    """
    anchor_results = (
        db.query(Result)
        .filter(Result.report_id == report.id, Result.test_alias_id.isnot(None))
        .order_by(Result.created_at)
        .all()
    )
    alias_ids: list = []
    seen = set()
    for result in anchor_results:
        if result.test_alias_id not in seen:
            seen.add(result.test_alias_id)
            alias_ids.append(result.test_alias_id)

    tests = []
    for alias_id in alias_ids:
        alias = db.query(TestAlias).filter(TestAlias.id == alias_id).one_or_none()
        if alias is None:
            continue

        rows = (
            db.query(Result, Report)
            .join(Report, Result.report_id == Report.id)
            .filter(
                Report.profile_id == report.profile_id,
                Result.test_alias_id == alias_id,
            )
            .order_by(Report.created_at.asc())
            .all()
        )
        if not rows:
            continue

        chart_unit = _pick_chart_unit(alias, rows)

        points = []
        excluded_points = []
        for result, row_report in rows:
            entry_base = {
                "report_id": str(row_report.id),
                "date": row_report.created_at.isoformat(),
                "raw_value": result.value,
                "raw_unit": result.unit,
            }
            if result.value_numeric is None:
                excluded_points.append({**entry_base, "reason": "not a numeric value"})
                continue

            comparable = _comparable_value(
                float(result.value_numeric), result.unit, chart_unit
            )
            if comparable is None:
                excluded_points.append({**entry_base, "reason": "unit not comparable"})
                continue

            points.append({**entry_base, "value": comparable, "flag": result.flag})

        latest_result, latest_report = rows[-1]
        tests.append(
            {
                "test_alias_id": str(alias_id),
                "canonical_name": alias.canonical_name,
                "chart_unit": chart_unit,
                "latest": {
                    "report_id": str(latest_report.id),
                    "date": latest_report.created_at.isoformat(),
                    "value": latest_result.value,
                    "unit": latest_result.unit,
                    "flag": latest_result.flag,
                    "reference_range_text": latest_result.reference_range_text,
                },
                "has_trend": len(points) >= 2,
                "points": points,
                "excluded_points": excluded_points,
            }
        )

    return tests
