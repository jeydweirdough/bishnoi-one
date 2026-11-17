"""Journal entries wait for approval, and Finance has notifications.

- nbfi_journal_entries: status (approved / waiting / rejected), who posted it
  (their account, beside the name kept already), who decided and when, and why
  it was rejected. Every entry already there is approved, so no balance moves.
- nbfi_notifications: what's waiting on someone, or was done to their work.
- journal.approve isn't given to any starting role: the Administrator holds
  every permission already; other roles get it when it's ticked.

Decided 2026-10-22 (Plans/Plan - Journal approval and notifications). Written
as 0012 on our branch; renumbered 0013 when main's 0012 (invoice salesperson)
arrived the same day, so it runs after it.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

COLUMNS = (
    ("posted_by_id", sa.String(36)),
    ("decided_by", sa.String(120)),
    ("decided_by_id", sa.String(36)),
    ("decided_at", sa.DateTime(timezone=True)),
    ("rejected_reason", sa.String(300)),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    have = {c["name"] for c in inspector.get_columns("nbfi_journal_entries")}
    if "status" not in have and bind.dialect.name == "sqlite":
        # In place on SQLite (2026-10-23): rebuilding the table to add the foreign keys drops
        # the old one, and its ON DELETE CASCADE would delete every journal line. The model
        # keeps the foreign keys; SQLite adds the columns without them.
        op.add_column("nbfi_journal_entries", sa.Column("status", sa.String(10), nullable=False, server_default="approved"))
        for name, kind in COLUMNS:
            op.add_column("nbfi_journal_entries", sa.Column(name, kind, nullable=True))
        op.create_index("ix_nbfi_journal_entries_status", "nbfi_journal_entries", ["status"])
    elif "status" not in have:
        with op.batch_alter_table("nbfi_journal_entries") as batch:
            batch.add_column(sa.Column("status", sa.String(10), nullable=False, server_default="approved"))
            for name, kind in COLUMNS:
                batch.add_column(sa.Column(name, kind, nullable=True))
            batch.create_foreign_key("nbfi_journal_entries_posted_by_id_fkey", "nbfi_users", ["posted_by_id"], ["id"], ondelete="SET NULL")
            batch.create_foreign_key("nbfi_journal_entries_decided_by_id_fkey", "nbfi_users", ["decided_by_id"], ["id"], ondelete="SET NULL")
            batch.create_index("ix_nbfi_journal_entries_status", ["status"])

    if "nbfi_notifications" not in inspector.get_table_names():
        op.create_table(
            "nbfi_notifications",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("text", sa.String(300), nullable=False),
            sa.Column("link", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("nbfi_notifications_inbox", "nbfi_notifications", ["user_id", "read_at"])
        op.create_index("ix_nbfi_notifications_created_at", "nbfi_notifications", ["created_at"])


def downgrade() -> None:
    op.drop_table("nbfi_notifications")
    with op.batch_alter_table("nbfi_journal_entries") as batch:
        batch.drop_index("ix_nbfi_journal_entries_status")
        batch.drop_constraint("nbfi_journal_entries_decided_by_id_fkey", type_="foreignkey")
        batch.drop_constraint("nbfi_journal_entries_posted_by_id_fkey", type_="foreignkey")
        for name, _ in reversed(COLUMNS):
            batch.drop_column(name)
        batch.drop_column("status")
