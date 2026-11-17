"""Printed quotations and orders raised from quotes.

- nbcm_sales_settings: the company's address, TIN and contact details, for
  the letterhead of a printed quotation.
- nbcm_quotes.sales_order: the order Nabhi Order made from the quote (its id,
  number and link), so a quote is ordered once.

Each step only if it isn't done yet, like 0015.

Revision ID: 0021
Revises: 0020
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = lambda table: {c["name"] for c in inspector.get_columns(table)}  # noqa: E731
    have = columns("nbcm_sales_settings")
    with op.batch_alter_table("nbcm_sales_settings") as batch:
        if "company_address" not in have:
            batch.add_column(sa.Column("company_address", sa.String(300), nullable=True))
        if "company_tin" not in have:
            batch.add_column(sa.Column("company_tin", sa.String(40), nullable=True))
        if "company_contact" not in have:
            batch.add_column(sa.Column("company_contact", sa.String(200), nullable=True))
    if "sales_order" not in columns("nbcm_quotes"):
        with op.batch_alter_table("nbcm_quotes") as batch:
            batch.add_column(sa.Column("sales_order", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_quotes") as batch:
        batch.drop_column("sales_order")
    with op.batch_alter_table("nbcm_sales_settings") as batch:
        batch.drop_column("company_contact")
        batch.drop_column("company_tin")
        batch.drop_column("company_address")
