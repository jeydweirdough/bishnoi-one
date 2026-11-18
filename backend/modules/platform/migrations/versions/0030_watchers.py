"""Who monitors whom (2026-11-18, step 4E): nbpl_watchers, one new table. Filled at once from today's chart
(modules/platform/watchers.record: every head above each person and who they report to, source "chart"); from then on
the chart only adds to it, and administrators add or remove watchers by hand. Nothing else changes.

Revision ID: 0030
Revises: 0029
"""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "nbpl_watchers" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "nbpl_watchers",
            sa.Column("watched_id", sa.String(36), sa.ForeignKey("nbpl_identities.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("watcher_id", sa.String(36), sa.ForeignKey("nbpl_identities.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("source", sa.String(8), nullable=False),
            sa.Column("added_by", sa.String(254), nullable=True),
            sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("source IN ('chart', 'added')", name="nbpl_watcher_source"),
        )
        op.create_index("ix_nbpl_watchers_watcher_id", "nbpl_watchers", ["watcher_id"])
    from modules.platform import watchers

    watchers.record(bind.execute)


def downgrade() -> None:
    op.drop_index("ix_nbpl_watchers_watcher_id", table_name="nbpl_watchers")
    op.drop_table("nbpl_watchers")
