"""Business events (feature plan step 7): the events Inventory sends (its outbox, kept in the same
transaction as each change) and the ids of those it has taken (so each is taken once).

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

PREFIX = "nbin"


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if f"{PREFIX}_events_out" not in tables:
        op.create_table(
            f"{PREFIX}_events_out",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("slug", sa.String(40)),
            sa.Column("kind", sa.String(60), nullable=False),
            sa.Column("data", sa.JSON(), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), index=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.String(300)),
        )
    if f"{PREFIX}_events_in" not in tables:
        op.create_table(
            f"{PREFIX}_events_in",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("kind", sa.String(60), nullable=False),
            sa.Column("source", sa.String(40), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table(f"{PREFIX}_events_in")
    op.drop_table(f"{PREFIX}_events_out")
