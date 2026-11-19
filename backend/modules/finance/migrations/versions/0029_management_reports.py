"""The last management reports (feature plan step 17, 2026-10-29).

- nbfi_accounts.cost_behaviour: an expense that's fixed (rent, salaries) or variable (moves with sales), for
  break-even; nbfi_accounts.report_tag: depreciation, amortisation, interest, income tax (added back for
  EBITDA) or sales and marketing (customer acquisition cost).
- nbfi_fixed_assets: the asset register, depreciated straight-line each month to accumulated depreciation.
- nbfi_budgets: a fiscal year's budget per account (and division, when set), month by month.

Added in place: on SQLite a table rebuild drops what points at it.

Revision ID: 0029
Revises: 0028
"""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    have = {c["name"] for c in sa.inspect(bind).get_columns("nbfi_accounts")}
    for name, size in (("cost_behaviour", 8), ("report_tag", 20)):
        if name not in have:
            op.add_column("nbfi_accounts", sa.Column(name, sa.String(size)))
    tables = set(sa.inspect(bind).get_table_names())
    if "nbfi_fixed_assets" not in tables:
        op.create_table(
            "nbfi_fixed_assets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("asset_account_id", sa.String(36), sa.ForeignKey("nbfi_accounts.id"), nullable=False),
            sa.Column("accumulated_account_id", sa.String(36), sa.ForeignKey("nbfi_accounts.id"), nullable=False),
            sa.Column("expense_account_id", sa.String(36), sa.ForeignKey("nbfi_accounts.id"), nullable=False),
            sa.Column("cost_centavos", sa.Integer(), nullable=False),
            sa.Column("salvage_centavos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("acquired_on", sa.Date(), nullable=False),
            sa.Column("useful_months", sa.Integer(), nullable=False),
            sa.Column("depreciated_until", sa.Date()),
            sa.Column("accumulated_centavos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(10), nullable=False, server_default="active"),
            sa.Column("division_name", sa.String(120)),
            sa.Column("notes", sa.String(500)),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("useful_months > 0", name="fixed_asset_months"),
            sa.CheckConstraint("status IN ('active', 'disposed')", name="fixed_asset_status"),
        )
    if "nbfi_budgets" not in tables:
        op.create_table(
            "nbfi_budgets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("year_end", sa.Date(), nullable=False, index=True),
            sa.Column("account_id", sa.String(36), sa.ForeignKey("nbfi_accounts.id"), nullable=False),
            sa.Column("division_name", sa.String(120), nullable=False, server_default=""),
            sa.Column("months", sa.JSON(), nullable=False),
            sa.Column("updated_by", sa.String(120), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("year_end", "account_id", "division_name", name="budget_line"),
        )


def downgrade() -> None:
    op.drop_table("nbfi_budgets")
    op.drop_table("nbfi_fixed_assets")
    with op.batch_alter_table("nbfi_accounts") as batch:
        batch.drop_column("report_tag")
        batch.drop_column("cost_behaviour")
