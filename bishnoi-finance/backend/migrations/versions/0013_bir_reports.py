"""BIR reports, first part (decided 2026-10-24, from Oojeema's BIR features):
what the BIR's forms and books need that wasn't kept yet.

- The tax profile's RDO code and the month the fiscal year ends (December for
  a calendar year): on every BIR form and summary list.
- Creditable withholding a customer deducts from what they pay (their BIR Form
  2307 to us): its amount, ATC and the certificate, on the payment. It posts to
  1210 Creditable withholding tax (an asset: it's credited against our income
  tax), so what the customer owes goes down by the whole of it. The SAWT lists them.
- bir.view: the books of accounts, statements, VAT return and summary lists.

Revision ID: 0013
Revises: 0012
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

STAFF_ID = "00000000-0000-4000-8000-00000000f002"
AUDITOR_ID = "00000000-0000-4000-8000-00000000f003"
CWT = ("1210", "Creditable withholding tax", "asset")


def upgrade() -> None:
    db = op.get_bind()
    with op.batch_alter_table("nbfi_tax_profile") as batch:
        batch.add_column(sa.Column("rdo_code", sa.String(3), nullable=True))
        batch.add_column(sa.Column("fiscal_month_end", sa.Integer(), nullable=False, server_default="12"))
    with op.batch_alter_table("nbfi_invoice_payments") as batch:
        batch.add_column(sa.Column("cwt_centavos", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("cwt_atc", sa.String(8), nullable=True))
        batch.add_column(sa.Column("cwt_certificate", sa.String(60), nullable=True))
    op.add_column("nbfi_ledger_settings", sa.Column("cwt_account_id", sa.String(36), nullable=True))

    code, name, type_ = CWT
    if db.execute(sa.text("SELECT id FROM nbfi_accounts WHERE code = :c"), {"c": code}).scalar() is None:
        values = {"id": str(uuid.uuid4()), "c": code, "n": name, "t": type_, "a": True, "at": datetime.now(UTC)}
        if db.dialect.name == "sqlite":
            # SQLite has no sequence for the record number: the next one, as the app gives it (app/numbering.py).
            values["no"] = (db.execute(sa.text("SELECT MAX(no) FROM nbfi_accounts")).scalar() or 40000000) + 1
            db.execute(sa.text("INSERT INTO nbfi_accounts (id, no, code, name, type, description, is_active, created_at) VALUES (:id, :no, :c, :n, :t, NULL, :a, :at)"), values)
        else:
            db.execute(sa.text("INSERT INTO nbfi_accounts (id, code, name, type, description, is_active, created_at) VALUES (:id, :c, :n, :t, NULL, :a, :at)"), values)
    account = db.execute(sa.text("SELECT id FROM nbfi_accounts WHERE code = :c AND is_active"), {"c": code}).scalar()
    if account:
        db.execute(sa.text("UPDATE nbfi_ledger_settings SET cwt_account_id = :a WHERE id = 1 AND cwt_account_id IS NULL"), {"a": account})

    for role in (STAFF_ID, AUDITOR_ID):
        if db.execute(sa.text("SELECT id FROM nbfi_roles WHERE id = :r"), {"r": role}).scalar() is None:
            continue
        if db.execute(sa.text("SELECT 1 FROM nbfi_role_permissions WHERE role_id = :r AND permission = 'bir.view'"), {"r": role}).scalar() is None:
            db.execute(sa.text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES (:r, 'bir.view')"), {"r": role})


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission = 'bir.view'"))
    with op.batch_alter_table("nbfi_ledger_settings") as batch:
        batch.drop_column("cwt_account_id")
    with op.batch_alter_table("nbfi_invoice_payments") as batch:
        batch.drop_column("cwt_certificate")
        batch.drop_column("cwt_atc")
        batch.drop_column("cwt_centavos")
    with op.batch_alter_table("nbfi_tax_profile") as batch:
        batch.drop_column("fiscal_month_end")
        batch.drop_column("rdo_code")
