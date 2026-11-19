"""Signing in with a Nabhi account (the platform): each person's link to their
Nabhi account, and the passes already taken (each works once).

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    # A plain added column and a unique index: SQLite adds both in place, where a
    # batch change would copy the whole users table, which every other table points at.
    if "platform_identity_id" not in {c["name"] for c in inspector.get_columns("nbin_users")}:
        op.add_column("nbin_users", sa.Column("platform_identity_id", sa.String(36), nullable=True))
    if "uq_nbin_users_platform_identity" not in {i["name"] for i in inspector.get_indexes("nbin_users")}:
        op.create_index("uq_nbin_users_platform_identity", "nbin_users", ["platform_identity_id"], unique=True)
    if "nbin_platform_passes" not in inspector.get_table_names():
        op.create_table(
            "nbin_platform_passes",
            sa.Column("jti", sa.String(64), primary_key=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        )


def downgrade() -> None:
    op.drop_table("nbin_platform_passes")
    op.drop_index("uq_nbin_users_platform_identity", table_name="nbin_users")
    with op.batch_alter_table("nbin_users") as batch:
        batch.drop_column("platform_identity_id")
