"""Payments against invoices, and who may record them (benchmarks D4, E5).

- nbfi_invoice_payments: money received against an invoice, posted as it's
  recorded; one taken off stays, marked, with its reversal posted;
- invoices.collect, given to Finance Staff where the role already exists.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

STAFF_ID = "00000000-0000-4000-8000-00000000f002"


def upgrade() -> None:
    db = op.get_bind()
    if "nbfi_invoice_payments" not in sa.inspect(db).get_table_names():
        op.create_table(
            "nbfi_invoice_payments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("invoice_id", sa.String(36), sa.ForeignKey("nbfi_invoices.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("paid_on", sa.Date(), nullable=False),
            sa.Column("amount_centavos", sa.Integer(), nullable=False),
            sa.Column("method", sa.String(10), nullable=False),
            sa.Column("reference", sa.String(80), nullable=True),
            sa.Column("entry_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("recorded_by", sa.String(120), nullable=False),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("removed_by", sa.String(120), nullable=True),
        )
    have_staff = db.execute(sa.text("SELECT id FROM nbfi_roles WHERE id = :r"), {"r": STAFF_ID}).scalar()
    granted = db.execute(sa.text("SELECT 1 FROM nbfi_role_permissions WHERE role_id = :r AND permission = 'invoices.collect'"), {"r": STAFF_ID}).scalar()
    if have_staff and not granted:
        db.execute(sa.text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES (:r, 'invoices.collect')"), {"r": STAFF_ID})


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission = 'invoices.collect'"))
    op.drop_table("nbfi_invoice_payments")
