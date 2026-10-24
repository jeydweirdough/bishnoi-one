"""Supplier bills (decided 2026-10-24, BIR features from Oojeema, part two):
what the company owes Inventory's suppliers, the VAT on its purchases (input
VAT), and the expanded withholding it holds back for the BIR, with payments.

- nbfi_supplier_bills, nbfi_bill_payments.
- 1300 Input VAT (an asset: claimed against output VAT) and 2300 Expanded
  withholding tax payable (a liability: remitted with 0619E and 1601EQ), added
  if missing; 2000 Accounts payable already is. The default accounts point to them.
- bills.*: Finance Staff make, post and pay bills; the Auditor sees them.

Revision ID: 0014
Revises: 0013
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

FIRST = 40000001
STAFF_ID = "00000000-0000-4000-8000-00000000f002"
AUDITOR_ID = "00000000-0000-4000-8000-00000000f003"
GRANTS = {STAFF_ID: ["bills.view", "bills.create", "bills.record", "bills.pay"], AUDITOR_ID: ["bills.view"]}
NEW_ACCOUNTS = (("1300", "Input VAT", "asset"), ("2300", "Expanded withholding tax payable", "liability"))
POSTING = {"payables_account_id": "2000", "input_tax_account_id": "1300", "ewt_payable_account_id": "2300"}


def upgrade() -> None:
    db = op.get_bind()
    op.create_table(
        "nbfi_supplier_bills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("no", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft", index=True),
        sa.Column("supplier_id", sa.String(36), nullable=False, index=True),
        sa.Column("supplier_name", sa.String(160), nullable=False),
        sa.Column("supplier_tin", sa.String(20), nullable=True),
        sa.Column("supplier_address", sa.String(300), nullable=True),
        sa.Column("supplier_vat_status", sa.String(8), nullable=False, server_default="vat"),
        sa.Column("supplier_invoice_no", sa.String(60), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False, index=True),
        sa.Column("terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("delivery_ref", sa.String(60), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("amounts_include_vat", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("lines", sa.JSON(), nullable=False),
        sa.Column("atc", sa.String(8), nullable=True),
        sa.Column("ewt_rate_bp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("computed", sa.JSON(), nullable=True),
        sa.Column("total_centavos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tax_centavos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ewt_centavos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payable_centavos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paid_centavos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entry_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_by", sa.String(120), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", sa.String(120), nullable=True),
        sa.Column("void_reason", sa.String(300), nullable=True),
        sa.CheckConstraint("status IN ('draft', 'posted', 'void')", name="bill_status"),
    )
    op.create_index("nbfi_supplier_bills_no", "nbfi_supplier_bills", ["no"], unique=True)
    if db.dialect.name == "postgresql":
        seq = "nbfi_supplier_bills_no_seq"
        db.execute(sa.text(f"create sequence if not exists {seq} start with {FIRST}"))
        db.execute(sa.text(f"alter table nbfi_supplier_bills alter column no set default nextval('{seq}')"))
        db.execute(sa.text(f"alter sequence {seq} owned by nbfi_supplier_bills.no"))
    op.create_table(
        "nbfi_bill_payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bill_id", sa.String(36), sa.ForeignKey("nbfi_supplier_bills.id", ondelete="CASCADE"), nullable=False, index=True),
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

    stamp = datetime.now(UTC)
    for code, name, type_ in NEW_ACCOUNTS:
        if db.execute(sa.text("SELECT id FROM nbfi_accounts WHERE code = :c"), {"c": code}).scalar() is None:
            values = {"id": str(uuid.uuid4()), "c": code, "n": name, "t": type_, "a": True, "at": stamp}
            if db.dialect.name == "sqlite":
                values["no"] = (db.execute(sa.text("SELECT MAX(no) FROM nbfi_accounts")).scalar() or FIRST - 1) + 1
                db.execute(sa.text("INSERT INTO nbfi_accounts (id, no, code, name, type, description, is_active, created_at) VALUES (:id, :no, :c, :n, :t, NULL, :a, :at)"), values)
            else:
                db.execute(sa.text("INSERT INTO nbfi_accounts (id, code, name, type, description, is_active, created_at) VALUES (:id, :c, :n, :t, NULL, :a, :at)"), values)
    for column, code in POSTING.items():
        op.add_column("nbfi_ledger_settings", sa.Column(column, sa.String(36), nullable=True))
        account = db.execute(sa.text("SELECT id FROM nbfi_accounts WHERE code = :c AND is_active"), {"c": code}).scalar()
        if account:
            db.execute(sa.text(f"UPDATE nbfi_ledger_settings SET {column} = :a WHERE id = 1 AND {column} IS NULL"), {"a": account})

    for role, permissions in GRANTS.items():
        if db.execute(sa.text("SELECT id FROM nbfi_roles WHERE id = :r"), {"r": role}).scalar() is None:
            continue
        for p in permissions:
            if db.execute(sa.text("SELECT 1 FROM nbfi_role_permissions WHERE role_id = :r AND permission = :p"), {"r": role, "p": p}).scalar() is None:
                db.execute(sa.text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES (:r, :p)"), {"r": role, "p": p})


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission LIKE 'bills.%'"))
    with op.batch_alter_table("nbfi_ledger_settings") as batch:
        for column in POSTING:
            batch.drop_column(column)
    op.drop_table("nbfi_bill_payments")
    op.drop_table("nbfi_supplier_bills")
