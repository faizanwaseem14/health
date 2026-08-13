"""
Resolves a result's test name against the test_aliases catalog - a
plain lookup, never a decision. The catalog itself (starter data today,
potentially a full LOINC import later - see seed_data.py) is the only
thing that decides what maps to what; this file just normalizes
formatting and matches.
"""

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Result, TestAlias


def normalize_test_name(name: str) -> str:
    """
    Lowercased, single-spaced, trailing period stripped - so "Hgb",
    "HGB", " Hgb ", "Hgb." all match the same catalog entry. Purely a
    formatting normalization (whitespace, case, a trailing abbreviation
    dot), never a decision about what the name means.
    """
    collapsed = re.sub(r"\s+", " ", name.strip())
    return collapsed.rstrip(".").lower()


def resolve_aliases_for_report(db: Session, report_id: UUID) -> None:
    """
    For every result in the report, looks up its raw_test_name against
    test_aliases and, on a match, sets test_alias_id to that alias's
    row. If the raw name isn't in the catalog, falls back to trying the
    AI's own canonical_test_name guess (app/ai/service.py) - still a
    plain catalog lookup, not the AI's guess being trusted directly.

    A result whose name isn't in the catalog under either form simply
    keeps test_alias_id as None - nothing here invents a match.
    """
    results = db.query(Result).filter(Result.report_id == report_id).all()
    if not results:
        return

    aliases_by_name = {
        normalize_test_name(alias.raw_name): alias
        for alias in db.query(TestAlias).all()
    }

    for result in results:
        alias = aliases_by_name.get(normalize_test_name(result.raw_test_name))
        if alias is None and result.canonical_test_name:
            alias = aliases_by_name.get(normalize_test_name(result.canonical_test_name))
        result.test_alias_id = alias.id if alias is not None else None

    db.commit()
