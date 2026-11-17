"""Why an automatic purchase order was made (2026-11-18, owner's Step 2): nbin_purchase_orders.reason, read-only,
apart from the buyer's own notes. Existing order-on-demand and replenishment orders move their system sentence
from notes into reason, so notes are left for the buyer. Added in place.

Revision ID: 0026
Revises: 0025
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

SYSTEM = ("Order-on-demand for ", "Made by replenishment: ")


def upgrade() -> None:
    op.add_column("nbin_purchase_orders", sa.Column("reason", sa.Text(), nullable=True))
    pos = sa.table("nbin_purchase_orders", sa.column("id", sa.String), sa.column("notes", sa.Text), sa.column("reason", sa.Text))
    bind = op.get_bind()
    for row in bind.execute(sa.select(pos.c.id, pos.c.notes).where(pos.c.notes.isnot(None))).all():
        first, _, rest = (row.notes or "").partition("\n")
        if first.startswith(SYSTEM):
            bind.execute(pos.update().where(pos.c.id == row.id).values(reason=first, notes=rest.strip() or None))


def downgrade() -> None:
    op.drop_column("nbin_purchase_orders", "reason")
