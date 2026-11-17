"""Several mailboxes per person (Zoho Mail for work, Gmail for another), one
of them the default: the one-per-person table becomes one row per mailbox.

Revision ID: 0045
Revises: 0044
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    have = sa.inspect(bind).get_table_names()
    if "nbcm_mail_accounts" not in have:
        accounts = op.create_table(
            "nbcm_mail_accounts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("address", sa.String(254), nullable=False),
            sa.Column("values", sa.JSON, nullable=False),
            sa.Column("secrets", sa.Text, nullable=True),
            sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_error", sa.String(300), nullable=True),
            sa.UniqueConstraint("user_id", "address", name="mail_account_once"),
        )
        if "nbcm_mailboxes" in have:
            old = sa.table("nbcm_mailboxes", *(sa.column(c) for c in ("user_id", "provider", "address", "values", "secrets", "connected_at", "last_error")))
            rows = [dict(r._mapping) for r in bind.execute(sa.select(old))]
            if rows:
                op.bulk_insert(accounts, [{**r, "id": str(uuid.uuid4()), "is_default": True} for r in rows])
    if "nbcm_mailboxes" in have:
        op.drop_table("nbcm_mailboxes")


def downgrade() -> None:
    op.drop_table("nbcm_mail_accounts")
