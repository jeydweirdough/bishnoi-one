"""Nabhi accounts: a password for each person at the companies, and their
sign-ins, so one account opens every application they have been given.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("nbpl_identities")}
    with op.batch_alter_table("nbpl_identities") as batch:
        if "password_hash" not in columns:
            batch.add_column(sa.Column("password_hash", sa.String(255), nullable=True))
        if "password_changed_at" not in columns:
            batch.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    if "nbpl_identity_sessions" not in inspector.get_table_names():
        op.create_table(
            "nbpl_identity_sessions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("identity_id", sa.String(36), sa.ForeignKey("nbpl_identities.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("nbpl_identity_sessions")
    with op.batch_alter_table("nbpl_identities") as batch:
        batch.drop_column("password_changed_at")
        batch.drop_column("password_hash")
