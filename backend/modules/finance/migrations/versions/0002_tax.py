"""Tax: the company's registration (nbfi_tax_profile) and dated rates
(nbfi_tax_rates). The rates themselves come from each country's pack when
the API starts (app/tax/rates.py), so a pack's new rate needs no migration.

Each step only if it isn't done yet.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "nbfi_tax_profile" not in tables:
        op.create_table(
            "nbfi_tax_profile",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("country", sa.String(2), nullable=False),
            sa.Column("regime", sa.String(12), nullable=False),
            sa.Column("registered_name", sa.String(200), nullable=True),
            sa.Column("trade_name", sa.String(200), nullable=True),
            sa.Column("tin", sa.String(11), nullable=True),
            sa.Column("branch_code", sa.String(5), nullable=False),
            sa.Column("registered_address", sa.String(300), nullable=True),
            sa.Column("prices_include_tax", sa.Boolean(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_by_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.CheckConstraint("id = 1", name="one_tax_profile"),
        )
    if "nbfi_tax_rates" not in tables:
        op.create_table(
            "nbfi_tax_rates",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("country", sa.String(2), nullable=False),
            sa.Column("code", sa.String(20), nullable=False, index=True),
            sa.Column("rate_bp", sa.Integer(), nullable=False),
            sa.Column("valid_from", sa.Date(), nullable=False),
            sa.Column("valid_to", sa.Date(), nullable=True),
            sa.Column("source", sa.String(8), nullable=False),
            sa.Column("basis", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.UniqueConstraint("country", "code", "valid_from", name="tax_rate_start"),
        )


def downgrade() -> None:
    op.drop_table("nbfi_tax_rates")
    op.drop_table("nbfi_tax_profile")
