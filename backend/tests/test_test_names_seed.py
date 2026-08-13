"""
Tests for seed_test_aliases (app/test_names/seed.py) - the upsert
logic that loads SEED_ALIASES into test_aliases. No live database - db
is a MagicMock; the true "running it twice never duplicates rows"
guarantee is also verified for real against scratch Postgres (see the
Task summary for that run).
"""

import uuid
from unittest.mock import MagicMock, patch

from app.models import TestAlias
from app.test_names.seed import seed_test_aliases


def _fake_db(existing_aliases):
    fake_db = MagicMock()
    fake_db.query.return_value.all.return_value = existing_aliases
    return fake_db


_FAKE_SEED = [
    {
        "raw_name": "Hemoglobin",
        "canonical_name": "Hemoglobin",
        "category": "Hematology",
        "default_unit": "g/dL",
    },
    {
        "raw_name": "HGB",
        "canonical_name": "Hemoglobin",
        "category": "Hematology",
        "default_unit": "g/dL",
    },
]


def test_inserts_every_new_entry_when_the_table_is_empty():
    fake_db = _fake_db([])

    with patch("app.test_names.seed.SEED_ALIASES", _FAKE_SEED):
        inserted = seed_test_aliases(fake_db)

    assert inserted == 2
    assert fake_db.add.call_count == 2
    fake_db.commit.assert_called_once()


def test_does_not_reinsert_an_alias_that_already_exists():
    existing = TestAlias(
        id=uuid.uuid4(),
        raw_name="Hemoglobin",
        canonical_name="Hemoglobin",
        category="Hematology",
        default_unit="g/dL",
    )
    fake_db = _fake_db([existing])

    with patch("app.test_names.seed.SEED_ALIASES", _FAKE_SEED):
        inserted = seed_test_aliases(fake_db)

    # "Hemoglobin" already exists (1 skipped), "HGB" is new (1 inserted).
    assert inserted == 1
    assert fake_db.add.call_count == 1


def test_refreshes_an_existing_alias_to_match_updated_seed_data():
    existing = TestAlias(
        id=uuid.uuid4(),
        raw_name="Hemoglobin",
        canonical_name="Old Name",
        category="Old Category",
        default_unit="old-unit",
    )
    fake_db = _fake_db([existing])
    updated_seed = [
        {
            "raw_name": "Hemoglobin",
            "canonical_name": "Hemoglobin",
            "category": "Hematology",
            "default_unit": "g/dL",
        }
    ]

    with patch("app.test_names.seed.SEED_ALIASES", updated_seed):
        seed_test_aliases(fake_db)

    assert existing.canonical_name == "Hemoglobin"
    assert existing.category == "Hematology"
    assert existing.default_unit == "g/dL"
