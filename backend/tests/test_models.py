"""
Confirms the full database schema is defined correctly - all 13 tables
exist as SQLAlchemy models, and SQLAlchemy can generate valid CREATE
TABLE SQL for each one.

This test does NOT need a real database connection - it only checks the
model definitions themselves, so it runs the same locally, in CI, or
anywhere else with no Neon access required.
"""

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app import models  # noqa: F401 (import registers all tables on Base.metadata)
from app.database import Base

EXPECTED_TABLES = {
    "users",
    "profiles",
    "reports",
    "results",
    "corrections",
    "explanations",
    "jobs",
    "shares",
    "audit_log",
    "test_aliases",
    "otp_attempts",
    "ocr_words",
    "result_ocr_words",
}


def test_all_expected_tables_are_registered():
    assert set(Base.metadata.tables.keys()) == EXPECTED_TABLES


def test_every_table_compiles_to_valid_create_table_sql():
    dialect = postgresql.dialect()
    for table in Base.metadata.tables.values():
        # CreateTable(...).compile() raises an error if a table or column
        # definition is invalid, so simply not raising is the check.
        CreateTable(table).compile(dialect=dialect)


def test_results_flag_only_allows_low_normal_high():
    results_table = Base.metadata.tables["results"]
    check_constraints = [
        c.sqltext.text
        for c in results_table.constraints
        if c.__class__.__name__ == "CheckConstraint"
    ]
    assert any(
        "'low'" in c and "'normal'" in c and "'high'" in c for c in check_constraints
    )
    assert not any("critical" in c for c in check_constraints)


def test_results_trust_status_only_allows_trusted_or_review_required():
    results_table = Base.metadata.tables["results"]
    check_constraints = [
        c.sqltext.text
        for c in results_table.constraints
        if c.__class__.__name__ == "CheckConstraint"
    ]
    assert any("'trusted'" in c and "'review_required'" in c for c in check_constraints)
