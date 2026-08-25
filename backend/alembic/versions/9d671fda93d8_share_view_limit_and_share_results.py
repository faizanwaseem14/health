"""sharing: view limit column and share_results table

Adds the two pieces Group E's share links need that the Day 1 `shares`
table didn't yet have: a per-share view limit (max_views - NULL means
unlimited), and a join table for scoping a share to a chosen subset of
a report's results rather than the whole report.

Revision ID: 9d671fda93d8
Revises: c4b6a1e9f0d3
Create Date: 2026-08-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d671fda93d8"
down_revision: Union[str, None] = "c4b6a1e9f0d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shares", sa.Column("max_views", sa.Integer(), nullable=True))

    op.create_table(
        "share_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("share_id", sa.UUID(), nullable=False),
        sa.Column("result_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["share_id"], ["shares.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["result_id"], ["results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_share_results_share_id"), "share_results", ["share_id"], unique=False
    )
    op.create_index(
        op.f("ix_share_results_result_id"),
        "share_results",
        ["result_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_share_results_result_id"), table_name="share_results")
    op.drop_index(op.f("ix_share_results_share_id"), table_name="share_results")
    op.drop_table("share_results")
    op.drop_column("shares", "max_views")
