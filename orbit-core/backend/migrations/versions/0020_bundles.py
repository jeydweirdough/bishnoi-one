"""bundles: a set of products at one price

The old Orders app sells bundles — "Starter Pack: 2 x Amoxicillin + 1 x
Paracetamol, P1,800" — and Orbit had no idea what one was. It gives a bundle its
own code and also lists its items, so whether a bundle reads as one line or as
its parts is not a question with one right answer: it becomes a switch on each
bundle (`as_one_line`), and a company-wide default for new ones.

All new tables, so nothing already saved changes and promos are untouched.

Revision ID: 0020
Revises: 0019
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bundles",
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price_centavos", sa.Integer, nullable=False),
        sa.Column("as_one_line", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("starts_on", sa.Date, nullable=False),
        sa.Column("ends_on", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "id", name="bundle_in_company"),
        sa.UniqueConstraint("org_id", "code", name="bundle_code_in_company"),
        sa.CheckConstraint("price_centavos > 0", name="bundle_price"),
        sa.CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="bundle_dates"),
    )
    op.create_table(
        "bundle_items",
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("bundle_id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("product_id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("qty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["org_id", "bundle_id"], ["bundles.org_id", "bundles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id", "product_id"], ["products.org_id", "products.id"], ondelete="CASCADE"),
        sa.CheckConstraint("qty > 0", name="bundle_item_qty"),
    )
    op.create_table(
        "bundle_divisions",
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("bundle_id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("division_code", sa.String(32), primary_key=True, nullable=False),
        sa.ForeignKeyConstraint(["org_id", "bundle_id"], ["bundles.org_id", "bundles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id", "division_code"], ["divisions.org_id", "divisions.code"]),
    )
    op.create_table(
        "pricing_settings",
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), primary_key=True, nullable=False),
        sa.Column("bundles_as_one_line", sa.Boolean, nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_table("pricing_settings")
    op.drop_table("bundle_divisions")
    op.drop_table("bundle_items")
    op.drop_table("bundles")
