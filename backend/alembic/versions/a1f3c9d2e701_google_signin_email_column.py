"""google sign-in: nullable phone_number, add email column

Revision ID: a1f3c9d2e701
Revises: 99f1c66f4cf3
Create Date: 2026-08-17 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f3c9d2e701"
down_revision: Union[str, None] = "99f1c66f4cf3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Google (and other email-based) sign-in has no phone number at all,
    # so a user row can no longer require one.
    op.alter_column("users", "phone_number", existing_type=sa.String(), nullable=True)
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_column("users", "email")
    op.alter_column("users", "phone_number", existing_type=sa.String(), nullable=False)
