"""Approved materials (Media): files or links reps show customers, and who opened what.

Revision ID: 0041
Revises: 0040
"""

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = sa.inspect(op.get_bind()).get_table_names()
    if "nbcm_media" not in have:
        op.create_table(
            "nbcm_media",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("description", sa.String(500), nullable=True),
            sa.Column("file_ref", sa.String(32), nullable=True),
            sa.Column("file_name", sa.String(200), nullable=True),
            sa.Column("url", sa.String(1000), nullable=True),
            sa.Column("products", sa.JSON, nullable=False),
            sa.Column("only_teams", sa.JSON, nullable=False),
            sa.Column("approved_on", sa.String(10), nullable=False),
            sa.Column("expires_on", sa.String(10), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "nbcm_media_views" not in have:
        op.create_table(
            "nbcm_media_views",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("media_id", sa.String(36), sa.ForeignKey("nbcm_media.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("nbcm_companies.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False, index=True),
        )


def downgrade() -> None:
    op.drop_table("nbcm_media_views")
    op.drop_table("nbcm_media")
