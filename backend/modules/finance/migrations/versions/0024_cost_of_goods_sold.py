"""The cost of goods sold, booked with each invoice (decided 2026-10-28, feature plan step 3): two
default accounts (the expense, and the inventory it comes out of), and each invoice's cost.

Added in place, never by rebuilding a table (see 0017); safe to run twice.

Revision ID: 0024
Revises: 0023
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    db = op.get_bind()
    inspector = sa.inspect(db)
    postgres = db.dialect.name == "postgresql"
    have = {c["name"] for c in inspector.get_columns("nbfi_ledger_settings")}
    for column in ("cogs_account_id", "inventory_account_id"):
        if column not in have:
            op.add_column("nbfi_ledger_settings", sa.Column(column, sa.String(36), nullable=True))
            if postgres:
                op.create_foreign_key(f"nbfi_ledger_settings_{column}_fkey", "nbfi_ledger_settings", "nbfi_accounts", [column], ["id"], ondelete="SET NULL")
    have = {c["name"] for c in inspector.get_columns("nbfi_invoices")}
    if "cost_centavos" not in have:
        op.add_column("nbfi_invoices", sa.Column("cost_centavos", sa.Integer(), nullable=False, server_default="0"))
    if "line_costs" not in have:
        op.add_column("nbfi_invoices", sa.Column("line_costs", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbfi_invoices") as batch:
        batch.drop_column("line_costs")
        batch.drop_column("cost_centavos")
    with op.batch_alter_table("nbfi_ledger_settings") as batch:
        batch.drop_column("inventory_account_id")
        batch.drop_column("cogs_account_id")
