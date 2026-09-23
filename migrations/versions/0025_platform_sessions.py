"""a session that belongs to no company

A Developer Admin is not in any company, so signing in cannot put them in one.
Until now it did -- they landed in whichever company came first, which is how
you end up looking at Getmeds' settings when your job is the platform.

`sessions` is walled per company by design, so a session with no company needs
its own table rather than a nullable column: it is a different thing, not a
company session missing a field.

Revision ID: 0025
Revises: 0024
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_sessions",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_platform_sessions_user_id", "platform_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_platform_sessions_user_id", table_name="platform_sessions")
    op.drop_table("platform_sessions")
