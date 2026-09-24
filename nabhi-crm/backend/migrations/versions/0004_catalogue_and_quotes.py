"""The catalogue and quotes: products and their prices per price type, teams'
own prices, promos, bundles, guarantee-letter issuers, Sales' settings, and
quotes to companies and contacts.

Team Leads and Managers get the new "set team prices" permission (the
Administrator has every permission already).

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_types",
        sa.Column("code", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("entry", sa.String(8), nullable=False),
        sa.Column("rule", sa.String(8), nullable=False),
        sa.Column("requires_notes", sa.Boolean(), nullable=False),
        sa.Column("needs_approval", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint("entry IN ('list', 'entered')", name="price_type_entry"),
        sa.CheckConstraint("rule IN ('always', 'with_rx')", name="price_type_rule"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("generic_name", sa.String(160), nullable=True),
        sa.Column("strength", sa.String(60), nullable=True),
        sa.Column("form", sa.String(60), nullable=True),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "product_prices",
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("price_type_code", sa.String(40), sa.ForeignKey("price_types.code", ondelete="CASCADE"), primary_key=True),
        sa.Column("amount_centavos", sa.Integer(), nullable=False),
    )
    op.create_table(
        "team_price_types",
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("price_type_code", sa.String(40), sa.ForeignKey("price_types.code", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "team_prices",
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("price_type_code", sa.String(40), sa.ForeignKey("price_types.code", ondelete="CASCADE"), primary_key=True),
        sa.Column("amount_centavos", sa.Integer(), nullable=False),
    )
    op.create_table(
        "promos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("percent_bp", sa.Integer(), nullable=True),
        sa.Column("amount_centavos", sa.Integer(), nullable=True),
        sa.Column("buy_qty", sa.Integer(), nullable=True),
        sa.Column("free_qty", sa.Integer(), nullable=True),
        sa.Column("tiers", sa.JSON(), nullable=False),
        sa.Column("product_ids", sa.JSON(), nullable=True),
        sa.Column("starts_on", sa.String(10), nullable=True),
        sa.Column("ends_on", sa.String(10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('percent', 'amount', 'free_goods', 'tiered')", name="promo_kind"),
    )
    op.create_table(
        "bundles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price_centavos", sa.Integer(), nullable=False),
        sa.Column("as_one_line", sa.Boolean(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("starts_on", sa.String(10), nullable=True),
        sa.Column("ends_on", sa.String(10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "issuers",
        sa.Column("code", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    settings = op.create_table(
        "sales_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("discount_approval_bp", sa.Integer(), nullable=False),
        sa.Column("allows_guarantee_letters", sa.Boolean(), nullable=False),
        sa.Column("at_risk_days", sa.Integer(), nullable=False),
        sa.Column("lost_days", sa.Integer(), nullable=False),
    )
    op.bulk_insert(settings, [{"id": 1, "discount_approval_bp": 1000, "allows_guarantee_letters": True, "at_risk_days": 60, "lost_days": 90}])

    op.create_table(
        "quotes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("number", sa.String(24), nullable=False, unique=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=True),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("price_type", sa.String(40), nullable=False),
        sa.Column("price_type_name", sa.String(80), nullable=False),
        sa.Column("rx", sa.Boolean(), nullable=False),
        sa.Column("payer", sa.String(40), nullable=False),
        sa.Column("payer_name", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("lines", sa.JSON(), nullable=False),
        sa.Column("gross_centavos", sa.Integer(), nullable=False),
        sa.Column("promo_discount_centavos", sa.Integer(), nullable=False),
        sa.Column("discount_centavos", sa.Integer(), nullable=False),
        sa.Column("total_centavos", sa.Integer(), nullable=False),
        sa.Column("approval_status", sa.String(10), nullable=False),
        sa.Column("approval_reasons", sa.JSON(), nullable=False),
        sa.Column("approval_note", sa.Text(), nullable=True),
        sa.Column("approval_by_id", sa.String(36), nullable=True),
        sa.Column("approval_by_name", sa.String(120), nullable=True),
        sa.Column("approval_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("letter", sa.JSON(), nullable=True),
        sa.Column("letter_status", sa.String(10), nullable=False),
        sa.Column("letter_note", sa.Text(), nullable=True),
        sa.Column("letter_by_id", sa.String(36), nullable=True),
        sa.Column("letter_by_name", sa.String(120), nullable=True),
        sa.Column("letter_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_status", sa.String(10), nullable=False),
        sa.Column("paid_centavos", sa.Integer(), nullable=False),
        sa.Column("payments", sa.JSON(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("approval_status IN ('none', 'pending', 'approved', 'rejected')", name="quote_approval"),
        sa.CheckConstraint("letter_status IN ('none', 'pending', 'verified', 'rejected')", name="quote_letter"),
        sa.CheckConstraint("payment_status IN ('none', 'unpaid', 'partial', 'paid')", name="quote_payment"),
    )
    for column in ("company_id", "contact_id", "owner_id", "team_id", "approval_status", "letter_status", "payment_status", "created_at"):
        op.create_index(f"ix_quotes_{column}", "quotes", [column])

    # Setting a team's own prices: a lead's job, and a manager's.
    op.execute(
        "INSERT INTO role_permissions (role_id, permission) "
        "SELECT id, 'products.prices' FROM roles WHERE name IN ('Team Lead', 'Manager') AND is_system = false"
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission = 'products.prices'")
    op.drop_table("quotes")
    op.drop_table("sales_settings")
    op.drop_table("issuers")
    op.drop_table("bundles")
    op.drop_table("promos")
    op.drop_table("team_prices")
    op.drop_table("team_price_types")
    op.drop_table("product_prices")
    op.drop_table("products")
    op.drop_table("price_types")
