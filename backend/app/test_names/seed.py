"""
Upserts app/test_names/seed_data.py's starter aliases into the
test_aliases table - matched by raw_name (case/whitespace-insensitive,
via resolver.normalize_test_name), so running this after editing
SEED_ALIASES is always safe: existing rows get their canonical_name/
category/default_unit refreshed to match the seed data, new entries
get inserted, nothing is ever duplicated.

Run it with:

    python -m app.test_names.seed
"""

import logging

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import TestAlias
from app.test_names.resolver import normalize_test_name
from app.test_names.seed_data import SEED_ALIASES

logger = logging.getLogger("medvault")


def seed_test_aliases(db: Session) -> int:
    """Upserts every entry in SEED_ALIASES. Returns how many NEW rows
    were inserted (existing rows that were merely refreshed don't
    count)."""
    existing = {
        normalize_test_name(alias.raw_name): alias
        for alias in db.query(TestAlias).all()
    }

    inserted = 0
    for entry in SEED_ALIASES:
        key = normalize_test_name(entry["raw_name"])
        alias = existing.get(key)
        if alias is None:
            alias = TestAlias(raw_name=entry["raw_name"])
            db.add(alias)
            existing[key] = alias
            inserted += 1

        alias.canonical_name = entry["canonical_name"]
        alias.category = entry.get("category")
        alias.default_unit = entry.get("default_unit")

    db.commit()
    return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    session = SessionLocal()
    try:
        inserted_count = seed_test_aliases(session)
        logger.info(
            "Seeded test_aliases: %d new row(s), %d total entries in seed data.",
            inserted_count,
            len(SEED_ALIASES),
        )
    finally:
        session.close()
