"""Who made the sale on an invoice: the CRM's salesperson (their CRM id and name).

The CRM scores its people's sales from issued invoices (IST, sales days,
customers kept, new accounts, DSO), so each invoice says whose sale it is.
Picked from the CRM customer's owner when the invoice is made; an invoice with
none counts for nobody, as the playbooks say.

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nbfi_invoices") as batch:
        batch.add_column(sa.Column("salesperson_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("salesperson_name", sa.String(120), nullable=True))
        batch.create_index("ix_nbfi_invoices_salesperson_id", ["salesperson_id"])


def downgrade() -> None:
    with op.batch_alter_table("nbfi_invoices") as batch:
        batch.drop_index("ix_nbfi_invoices_salesperson_id")
        batch.drop_column("salesperson_name")
        batch.drop_column("salesperson_id")
