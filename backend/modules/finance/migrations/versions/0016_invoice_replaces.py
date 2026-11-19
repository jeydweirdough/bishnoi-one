"""Which cancelled invoice an invoice replaces (cancel and reissue).

- nbfi_invoices.replaces_id: the voided invoice this one corrects; unique, so
  a cancelled invoice has at most one replacement. Never printed on the invoice.

Rommel Q20: a posted invoice is never edited, it's cancelled and reissued.
Decided 2026-10-22 (Plans/Plan - Replaces invoice). Main's latest migration was
0012 when this was written (checked right before).

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "replaces_id" in {c["name"] for c in sa.inspect(bind).get_columns("nbfi_invoices")}:
        return
    if bind.dialect.name == "sqlite":
        # In place on SQLite (2026-10-23): rebuilding the table drops the old one, and its
        # ON DELETE CASCADE would delete every payment recorded on an invoice. The model keeps
        # the foreign key; a unique index keeps "one replacement each".
        op.add_column("nbfi_invoices", sa.Column("replaces_id", sa.String(36), nullable=True))
        op.create_index("nbfi_invoices_replaces_once", "nbfi_invoices", ["replaces_id"], unique=True)
        return
    with op.batch_alter_table("nbfi_invoices") as batch:
        batch.add_column(sa.Column("replaces_id", sa.String(36), nullable=True))
        batch.create_foreign_key("nbfi_invoices_replaces_id_fkey", "nbfi_invoices", ["replaces_id"], ["id"], ondelete="SET NULL")
        batch.create_unique_constraint("nbfi_invoices_replaces_once", ["replaces_id"])


def downgrade() -> None:
    with op.batch_alter_table("nbfi_invoices") as batch:
        batch.drop_constraint("nbfi_invoices_replaces_once", type_="unique")
        batch.drop_constraint("nbfi_invoices_replaces_id_fkey", type_="foreignkey")
        batch.drop_column("replaces_id")
