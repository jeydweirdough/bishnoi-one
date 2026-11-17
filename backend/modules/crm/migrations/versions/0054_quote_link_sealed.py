"""Order links can be copied again: the link is kept encrypted (with the
CONNECTIONS_KEY) beside its hash, for its maker to copy while it works.

Revision ID: 0054
Revises: 0053
"""

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "token_sealed" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_quote_links")}:
        return
    with op.batch_alter_table("nbcm_quote_links") as batch:
        batch.add_column(sa.Column("token_sealed", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_quote_links") as batch:
        batch.drop_column("token_sealed")
