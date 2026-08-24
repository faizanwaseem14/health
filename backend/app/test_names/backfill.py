"""
Re-runs catalog matching (resolve_aliases_for_report) against every
report that already has results, WITHOUT re-running OCR or the AI
extraction - for exactly one situation: test_aliases was seeded (or
extended) AFTER some reports were already processed, so their results
were resolved against an empty or incomplete catalog and are stuck with
test_alias_id = NULL forever unless something re-resolves them.

Safe to run any number of times: resolve_aliases_for_report() is a pure
re-computation from each result's stored raw_test_name against whatever
test_aliases currently holds, so re-running it after seed.py changes
nothing for a report that already matched, and picks up new matches for
one that didn't.

Run it with:

    python -m app.test_names.backfill
"""

import logging

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Result
from app.test_names.resolver import resolve_aliases_for_report

logger = logging.getLogger("medvault")


def backfill_alias_matches(db: Session) -> int:
    """Re-resolves every report that has at least one result. Returns
    how many reports were re-resolved."""
    report_ids = [row[0] for row in db.query(Result.report_id).distinct().all()]
    for report_id in report_ids:
        resolve_aliases_for_report(db, report_id)
    return len(report_ids)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    session = SessionLocal()
    try:
        report_count = backfill_alias_matches(session)
        logger.info(
            "Re-resolved catalog matches for %d report(s) already in the database.",
            report_count,
        )
    finally:
        session.close()
