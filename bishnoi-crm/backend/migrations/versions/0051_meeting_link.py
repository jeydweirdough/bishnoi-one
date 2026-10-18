"""A meeting's (or an online call's) link: Google Meet, Zoom or Teams, with a
Join button wherever the meeting shows.

Revision ID: 0051
Revises: 0050
"""

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_activities")}
    if "meeting_link" not in have:
        with op.batch_alter_table("nbcm_activities") as batch:
            batch.add_column(sa.Column("meeting_link", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_activities") as batch:
        batch.drop_column("meeting_link")
