"""Settings: custom fields on products, companies, contacts and quotes; the
pick-lists behind some dropdowns; and the company and quote settings an admin
changes in the app instead of in .env.

Revision ID: 0007
Revises: 0006
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

EXTRA = ("products", "companies", "contacts", "quotes")

LISTS = {
    "industry": ["Clinic", "Hospital", "Hospital group", "Retail pharmacy", "Distributor", "Government"],
    "product_form": ["Tablet", "Capsule", "Syrup", "Suspension", "Sachet", "Injection", "Cream", "Drops"],
    "product_unit": ["box", "bottle", "piece", "sachet", "vial", "tube", "pack"],
}


def upgrade() -> None:
    op.create_table(
        "custom_fields",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity", sa.String(12), nullable=False),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("in_list", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("entity", "key", name="uq_custom_field_key"),
        sa.CheckConstraint("entity IN ('product', 'company', 'contact', 'quote')", name="custom_field_entity"),
        sa.CheckConstraint("type IN ('text', 'long_text', 'number', 'date', 'choice', 'yes_no')", name="custom_field_type"),
    )
    items = op.create_table(
        "pick_list_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("list", sa.String(30), nullable=False, index=True),
        sa.Column("value", sa.String(80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("list", "value", name="uq_pick_list_value"),
    )
    op.bulk_insert(
        items,
        [{"id": str(uuid.uuid4()), "list": name, "value": v, "sort_order": n, "is_active": True} for name, values in LISTS.items() for n, v in enumerate(values)],
    )
    for table in EXTRA:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("extra", sa.JSON(), nullable=False, server_default="{}"))
    with op.batch_alter_table("quotes") as batch:
        batch.add_column(sa.Column("valid_until", sa.String(10), nullable=True))
        batch.add_column(sa.Column("terms", sa.Text(), nullable=True))
    with op.batch_alter_table("sales_settings") as batch:
        # Null: what .env says.
        batch.add_column(sa.Column("org_name", sa.String(120), nullable=True))
        batch.add_column(sa.Column("currency", sa.String(3), nullable=True))
        batch.add_column(sa.Column("locale", sa.String(20), nullable=True))
        batch.add_column(sa.Column("timezone", sa.String(60), nullable=True))
        batch.add_column(sa.Column("quote_prefix", sa.String(10), nullable=False, server_default="Q"))
        batch.add_column(sa.Column("quote_valid_days", sa.Integer(), nullable=False, server_default="30"))
        batch.add_column(sa.Column("quote_terms", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sales_settings") as batch:
        for c in ("quote_terms", "quote_valid_days", "quote_prefix", "timezone", "locale", "currency", "org_name"):
            batch.drop_column(c)
    with op.batch_alter_table("quotes") as batch:
        batch.drop_column("terms")
        batch.drop_column("valid_until")
    for table in EXTRA:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("extra")
    op.drop_table("pick_list_items")
    op.drop_table("custom_fields")
