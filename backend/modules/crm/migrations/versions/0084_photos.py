"""Optional photos everywhere (2026-11-18, owner's Step 4B): nbcm_photos keeps photos of a visit. target_type +
target_id, no foreign key to the visit. A new table only: nothing rebuilt.

Revision ID: 0084
Revises: 0083
"""

import sqlalchemy as sa
from alembic import op

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbcm_photos" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "nbcm_photos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("taken_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_nbcm_photos_target", "nbcm_photos", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_nbcm_photos_target", table_name="nbcm_photos")
    op.drop_table("nbcm_photos")
