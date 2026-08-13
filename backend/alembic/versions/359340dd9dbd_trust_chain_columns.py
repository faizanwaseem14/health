"""trust chain columns

Adds the two columns the trust chain (app/trust/) writes to every
result row: trust_status ("trusted" or "review_required" - fail-closed,
defaults to review_required so a row is never accidentally trusted
before the checks actually run) and trust_check_notes (which check
failed and why, for review_required rows).

Auto-generated from app/models/result.py, then hand-adjusted:
  - trust_status is added with a server-side default so this migration
    is safe to run against a `results` table that already has rows
    (existing rows get "review_required", same fail-closed default the
    model uses - they simply haven't been checked yet).
  - The CheckConstraint restricting trust_status to its two valid
    values isn't something Alembic's autogenerate detects on its own,
    so it's added here by hand, matching flag's existing
    ck_results_flag_valid_values constraint.

Revision ID: 359340dd9dbd
Revises: efd579912105
Create Date: 2026-08-13 16:19:51.489633

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "359340dd9dbd"
down_revision: Union[str, None] = "efd579912105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "results",
        sa.Column(
            "trust_status",
            sa.String(),
            nullable=False,
            server_default="review_required",
        ),
    )
    op.add_column("results", sa.Column("trust_check_notes", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_results_trust_status_valid_values",
        "results",
        "trust_status IN ('trusted', 'review_required')",
    )
    # The server_default above exists only to safely backfill any
    # existing rows during this migration; app/models/result.py sets
    # the same default at the ORM level for all new rows, so the
    # column doesn't need a permanent server-side default going forward.
    op.alter_column("results", "trust_status", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_results_trust_status_valid_values", "results", type_="check")
    op.drop_column("results", "trust_check_notes")
    op.drop_column("results", "trust_status")
