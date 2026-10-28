"""Current or long-term, on assets and liabilities (decided 2026-10-28, feature plan Track R):
working capital and the current and quick ratios (app/management.py) need it. Empty until set:
the account is then judged by its name.

Added in place, never by rebuilding a table (see 0017); safe to run twice.

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "term" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbfi_accounts")}:
        op.add_column("nbfi_accounts", sa.Column("term", sa.String(12), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbfi_accounts") as batch:
        batch.drop_column("term")
