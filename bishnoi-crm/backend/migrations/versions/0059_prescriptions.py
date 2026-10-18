"""Rx medicines need a prescription: a product says whether it does, and a quote
keeps the prescriptions attached to it (an order link's), as files in
nbcm_stored_files like a guarantee letter.

Revision ID: 0059
Revises: 0058
"""

import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspect = sa.inspect(op.get_bind())
    if "needs_prescription" not in {c["name"] for c in inspect.get_columns("nbcm_products")}:
        with op.batch_alter_table("nbcm_products") as batch:
            batch.add_column(sa.Column("needs_prescription", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "prescriptions" not in {c["name"] for c in inspect.get_columns("nbcm_quotes")}:
        with op.batch_alter_table("nbcm_quotes") as batch:
            batch.add_column(sa.Column("prescriptions", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_quotes") as batch:
        batch.drop_column("prescriptions")
    with op.batch_alter_table("nbcm_products") as batch:
        batch.drop_column("needs_prescription")
