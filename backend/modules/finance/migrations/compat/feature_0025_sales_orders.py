"""Local permission-based Sales Orders; no existing records or grants changed."""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("nbfi_sales_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("number", sa.String(40), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("customer_tin", sa.String(20)), sa.Column("customer_address", sa.String(300)),
        sa.Column("order_date", sa.Date(), nullable=False), sa.Column("reference", sa.String(80)),
        sa.Column("salesperson", sa.String(120)), sa.Column("terms_days", sa.Integer(), nullable=False),
        sa.Column("prices_include_tax", sa.Boolean(), nullable=False), sa.Column("lines", sa.JSON(), nullable=False),
        sa.Column("total_centavos", sa.Integer(), nullable=False), sa.Column("tax_centavos", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(1000)),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbfi_users.id"), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("submitted_by_id", sa.String(36), sa.ForeignKey("nbfi_users.id")),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_nbfi_sales_orders_status", "nbfi_sales_orders", ["status"])


def downgrade():
    pass  # Retain local approval evidence; never rebuild existing tables.
