"""Revenue by division (feature plan step 4, agreed 2026-10-28): each invoice keeps the division
and team of its salesperson, as the company's org chart had them when it was made (the CRM's
teams are the Platform's units, with the same ids). Kept on the invoice, so moving someone later
doesn't move their past sales.

Added in place, never by rebuilding a table (see 0017); safe to run twice.

Revision ID: 0025
Revises: 0024
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

COLUMNS = (("division_id", 36), ("division_name", 120), ("team_id", 36), ("team_name", 120))


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbfi_invoices")}
    for name, size in COLUMNS:
        if name not in have:
            op.add_column("nbfi_invoices", sa.Column(name, sa.String(size), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbfi_invoices") as batch:
        for name, _ in COLUMNS:
            batch.drop_column(name)
