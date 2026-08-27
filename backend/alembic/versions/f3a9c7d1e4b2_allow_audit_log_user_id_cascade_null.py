"""allow audit log user_id cascade null

The append-only trigger from 58984b0977b6 blocks EVERY update, with no
exception - but audit_log.user_id has ON DELETE SET NULL on its FK to
users.id (see 0c36bed19775), and Postgres implements that cascade as an
ordinary UPDATE under the hood, which the trigger was firing on and
rejecting. The practical effect: DELETE /auth/me (account deletion)
failed outright with a database error for any user who had ever
performed an audited action - which is effectively every real user,
since almost every route writes an audit_log row. Found while
verifying the full delete-account flow against a real database ahead
of deploy.

The fix narrows the trigger's exception to exactly that one legitimate,
system-driven case - an UPDATE that ONLY nulls out a previously-set
user_id, with every other column unchanged - while still refusing every
other UPDATE and every DELETE, so the append-only guarantee for the
audit trail's actual content is untouched.

Revision ID: f3a9c7d1e4b2
Revises: 9d671fda93d8
Create Date: 2026-08-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9c7d1e4b2"
down_revision: Union[str, None] = "9d671fda93d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'UPDATE'
               AND OLD.user_id IS NOT NULL
               AND NEW.user_id IS NULL
               AND NEW.id IS NOT DISTINCT FROM OLD.id
               AND NEW.action IS NOT DISTINCT FROM OLD.action
               AND NEW.resource_type IS NOT DISTINCT FROM OLD.resource_type
               AND NEW.resource_id IS NOT DISTINCT FROM OLD.resource_id
               AND NEW.ip_address IS NOT DISTINCT FROM OLD.ip_address
               AND NEW.user_agent IS NOT DISTINCT FROM OLD.user_agent
               AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
            THEN
                -- The one legitimate exception: the ON DELETE SET NULL
                -- cascade from users.id, firing when the account that
                -- performed this action is deleted. Every other field
                -- must be exactly what it always was.
                RETURN NEW;
            END IF;

            RAISE EXCEPTION
                'audit_log is append-only: % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_log is append-only: % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
