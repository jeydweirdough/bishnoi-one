"""The recycle bin (2026-10-30, app/recycle_bin.py): deleted records kept 30 days as snapshots, restorable.
One new table; nothing existing changes.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbad_recycle_bin" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "nbad_recycle_bin",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("record_id", sa.String(64), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("unlinked", sa.JSON(), nullable=False),
        sa.Column("deleted_by", sa.String(254), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_nbad_recycle_bin_expires_at", "nbad_recycle_bin", ["expires_at"])


def downgrade() -> None:
    op.drop_table("nbad_recycle_bin")
