"""Optional photos everywhere (2026-11-18, owner's Step 4B): nbin_photos keeps photos of a delivery (the goods, the
proof of delivery) and of its packages. target_type + target_id, no foreign key to the record shown. The courier's
proof-of-delivery photo on nbin_orders stays as it was. A new table only: nothing rebuilt.

Revision ID: 0029
Revises: 0028
"""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nbin_photos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("taken_by_id", sa.String(36), sa.ForeignKey("nbin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_nbin_photos_target", "nbin_photos", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_nbin_photos_target", "nbin_photos")
    op.drop_table("nbin_photos")
