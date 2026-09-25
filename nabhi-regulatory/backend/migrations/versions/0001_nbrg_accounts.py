"""Accounts and their sign-ins, as nbrg_users and nbrg_sessions.

A database from before migrations has them as plain `users` and `sessions`
(made by create_all); those are renamed and kept, with everyone in them.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "users" in tables and "sessions" in tables:
        op.rename_table("users", "nbrg_users")
        op.rename_table("sessions", "nbrg_sessions")
        return

    op.create_table(
        "nbrg_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'member')", name="user_role"),
    )
    op.create_table(
        "nbrg_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("nbrg_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_nbrg_sessions_user_id", "nbrg_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_table("nbrg_sessions")
    op.drop_table("nbrg_users")
