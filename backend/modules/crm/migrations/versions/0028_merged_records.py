"""Merging duplicates: where a merged customer or contact went, and pairs said
to be different so they aren't offered again.

Revision ID: 0028
Revises: 0027
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = set(sa.inspect(op.get_bind()).get_table_names())
    if "nbcm_merged_records" not in have:
        op.create_table(
            "nbcm_merged_records",
            sa.Column("old_id", sa.String(36), primary_key=True),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("new_id", sa.String(36), nullable=False, index=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("merged_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL")),
            sa.Column("merged_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "nbcm_not_duplicates" not in have:
        op.create_table(
            "nbcm_not_duplicates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("first_id", sa.String(36), nullable=False, index=True),
            sa.Column("second_id", sa.String(36), nullable=False, index=True),
            sa.Column("decided_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL")),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("kind", "first_id", "second_id", name="not_duplicate_once"),
        )


def downgrade() -> None:
    op.drop_table("nbcm_not_duplicates")
    op.drop_table("nbcm_merged_records")
