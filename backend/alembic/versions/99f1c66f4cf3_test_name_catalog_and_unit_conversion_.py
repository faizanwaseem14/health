"""test name catalog and unit conversion columns

Adds the two DERIVED columns app/units/ writes to a result row:
converted_value_numeric and converted_unit - a value expressed in the
canonical test catalog's (app/test_names/) standard unit, computed
only when a genuine, well-defined unit conversion applies. Both are
nullable with no default: they're additive/optional, never touching
the original `value`/`unit` columns, and safe to add to a `results`
table that already has rows (existing rows simply get NULL until the
pipeline runs for them again).

Auto-generated from app/models/result.py.

Revision ID: 99f1c66f4cf3
Revises: 359340dd9dbd
Create Date: 2026-08-13 17:29:22.526538

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "99f1c66f4cf3"
down_revision: Union[str, None] = "359340dd9dbd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "results", sa.Column("converted_value_numeric", sa.Numeric(), nullable=True)
    )
    op.add_column("results", sa.Column("converted_unit", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "converted_unit")
    op.drop_column("results", "converted_value_numeric")
