"""A default shipping fee per courier (2026-11-18, owner's Step 2): nbin_couriers.default_fee, in centavos,
filled into a delivery's fee when that courier is picked. Added in place; existing couriers start at 0.

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
    op.add_column("nbin_couriers", sa.Column("default_fee", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("nbin_couriers", "default_fee")
