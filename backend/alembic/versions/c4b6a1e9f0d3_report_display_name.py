"""report history: nullable display_name column

Revision ID: c4b6a1e9f0d3
Revises: a1f3c9d2e701
Create Date: 2026-08-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4b6a1e9f0d3"
down_revision: Union[str, None] = "a1f3c9d2e701"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A user-chosen label for a report, e.g. renaming "IMG_4821.jpg" to
    # "Blood work - March". NULL means "no override yet" - the report
    # history screen falls back to original_filename, never a blank
    # name.
    op.add_column("reports", sa.Column("display_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "display_name")
