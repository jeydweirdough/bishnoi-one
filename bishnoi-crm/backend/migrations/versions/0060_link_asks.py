"""An order link says what the customer must send (set by the rep making it): a
prescription always or for Rx medicines, a guarantee letter for a payer, and
named documents. A quote keeps those documents beside its prescriptions.

Revision ID: 0060
Revises: 0059
"""

import sqlalchemy as sa
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspect = sa.inspect(op.get_bind())
    if "asks" not in {c["name"] for c in inspect.get_columns("nbcm_quote_links")}:
        with op.batch_alter_table("nbcm_quote_links") as batch:
            batch.add_column(sa.Column("asks", sa.JSON(), nullable=True))
    if "documents" not in {c["name"] for c in inspect.get_columns("nbcm_quotes")}:
        with op.batch_alter_table("nbcm_quotes") as batch:
            batch.add_column(sa.Column("documents", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_quotes") as batch:
        batch.drop_column("documents")
    with op.batch_alter_table("nbcm_quote_links") as batch:
        batch.drop_column("asks")
