"""An application's connect key is delivered to the address registered for it
(Applications), not copied onto its server: it's kept encrypted here so it can
be delivered again when another copy of the application asks.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "connect_key_sealed" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbpl_applications")}:
        with op.batch_alter_table("nbpl_applications") as batch:
            batch.add_column(sa.Column("connect_key_sealed", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbpl_applications") as batch:
        batch.drop_column("connect_key_sealed")
