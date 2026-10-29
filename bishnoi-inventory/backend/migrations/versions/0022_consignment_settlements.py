"""Consignment settlements (feature plan step 15d, finished 2026-10-29): what sold from a vendor's consignment since
the last settlement, priced at the vendor's price, recorded once and sent to Finance as a draft vendor bill
(event consignment.billed). The next settlement starts where this one ended, so no sale is billed twice.

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbin_consignment_settlements" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "nbin_consignment_settlements",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("number", sa.String(20), nullable=False, unique=True),
            sa.Column("supplier_id", sa.String(36), sa.ForeignKey("nbin_suppliers.id"), nullable=False, index=True),
            sa.Column("from_at", sa.DateTime(timezone=True)),
            sa.Column("to_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("lines", sa.JSON(), nullable=False),
            sa.Column("total", sa.Integer(), nullable=False),
            sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbin_users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("nbin_consignment_settlements")
