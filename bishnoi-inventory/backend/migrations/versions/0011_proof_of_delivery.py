"""Proof of delivery (feature plan step 10, 2026-10-29): the customer signs for an issued order: who
received it, their signature (a PNG, black on transparent), when, and a fingerprint of the order then.

Added in place; safe to run twice.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

COLUMNS = (("received_by_name", sa.String(120)), ("received_signature", sa.LargeBinary()), ("received_signed_at", sa.DateTime(timezone=True)),
           ("received_fingerprint", sa.String(64)))


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbin_orders")}
    for name, kind in COLUMNS:
        if name not in have:
            op.add_column("nbin_orders", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbin_orders") as batch:
        for name, _ in COLUMNS:
            batch.drop_column(name)
