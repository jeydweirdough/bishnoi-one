"""Teams get headquarters: the offices a team (a division) works from, as a list.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("teams") as batch:
        batch.add_column(sa.Column("headquarters", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("teams") as batch:
        batch.drop_column("headquarters")
