"""Price rules (benchmarks/decisions.md, D4): ordered, dated conditions an
admin sets, with tax from Finance as the last step.

- nbcm_price_groups: groups of customers priced alike (Hospital, Drugstore chain).
- nbcm_companies.price_group_code: the group a company is in.
- nbcm_price_conditions: group prices, volume scales and surcharges, each dated.
- nbcm_products.vat_category: standard, zero_rated or exempt, for Finance's tax.
- nbcm_sales_settings.pricing_procedure, prices_include_tax: the order, and
  whether catalogue prices already include VAT.
- nbcm_quotes.tax: Finance's tax on the quote, as the invoice will show it.

Each step only if it isn't done yet, like 0015.

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    columns = lambda table: {c["name"] for c in inspector.get_columns(table)}  # noqa: E731

    if "nbcm_price_groups" not in tables:
        op.create_table(
            "nbcm_price_groups",
            sa.Column("code", sa.String(40), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False, unique=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )
    if "price_group_code" not in columns("nbcm_companies"):
        with op.batch_alter_table("nbcm_companies") as batch:
            batch.add_column(sa.Column("price_group_code", sa.String(40), nullable=True))
            batch.create_foreign_key("fk_company_price_group", "nbcm_price_groups", ["price_group_code"], ["code"], ondelete="SET NULL")
            batch.create_index("ix_nbcm_companies_price_group_code", ["price_group_code"])
    if "nbcm_price_conditions" not in tables:
        op.create_table(
            "nbcm_price_conditions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("kind", sa.String(12), nullable=False, index=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("nbcm_products.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("price_group_code", sa.String(40), sa.ForeignKey("nbcm_price_groups.code", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("price_type_code", sa.String(40), sa.ForeignKey("nbcm_price_types.code", ondelete="CASCADE"), nullable=True),
            sa.Column("amount_centavos", sa.Integer(), nullable=True),
            sa.Column("percent_bp", sa.Integer(), nullable=True),
            sa.Column("tiers", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("starts_on", sa.String(10), nullable=True),
            sa.Column("ends_on", sa.String(10), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("kind IN ('group_price', 'volume', 'surcharge')", name="condition_kind"),
        )
    if "vat_category" not in columns("nbcm_products"):
        with op.batch_alter_table("nbcm_products") as batch:
            batch.add_column(sa.Column("vat_category", sa.String(20), nullable=False, server_default="standard"))
    have = columns("nbcm_sales_settings")
    with op.batch_alter_table("nbcm_sales_settings") as batch:
        if "pricing_procedure" not in have:
            batch.add_column(sa.Column("pricing_procedure", sa.JSON(), nullable=True))
        if "prices_include_tax" not in have:
            batch.add_column(sa.Column("prices_include_tax", sa.Boolean(), nullable=False, server_default=sa.true()))
    if "tax" not in columns("nbcm_quotes"):
        with op.batch_alter_table("nbcm_quotes") as batch:
            batch.add_column(sa.Column("tax", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_quotes") as batch:
        batch.drop_column("tax")
    with op.batch_alter_table("nbcm_sales_settings") as batch:
        batch.drop_column("prices_include_tax")
        batch.drop_column("pricing_procedure")
    with op.batch_alter_table("nbcm_products") as batch:
        batch.drop_column("vat_category")
    op.drop_table("nbcm_price_conditions")
    with op.batch_alter_table("nbcm_companies") as batch:
        batch.drop_index("ix_nbcm_companies_price_group_code")
        batch.drop_constraint("fk_company_price_group", type_="foreignkey")
        batch.drop_column("price_group_code")
    op.drop_table("nbcm_price_groups")
