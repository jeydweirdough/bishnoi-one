"""Payables (suppliers and their bills) and a parent for each account.

- nbfi_accounts.parent_id: the account an account sits under, as Oojeema's chart
  groups them (the chart import reads it). Optional; nothing else changes.
- nbfi_suppliers, nbfi_bills, nbfi_bill_files: suppliers; their bills (draft,
  recorded, void), with the lines as entered and the amounts worked out; the
  supplier's invoice attached (the file itself goes in nbfi_stored_files).
- nbfi_ledger_settings: where a recorded bill posts (payables, input VAT, the tax
  withheld). Two starter accounts are added if their codes are free, 1300 Input VAT
  and 2300 Withholding tax payable - expanded, and set with 2000 Accounts payable.
- The starting roles: Finance Staff keeps suppliers and records bills; the Auditor
  sees them. Other roles are ticked on the Roles screen.

Nothing existing is changed or removed. Decided 2026-10-23 (Plans/Plan - Suppliers,
bills and chart import). Main's latest migration was 0012 when this was written
(checked right before).

Revision ID: 0017
Revises: 0016
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

FIRST = 40000001
NEW_ACCOUNTS = (("1300", "Input VAT", "asset"), ("2300", "Withholding tax payable - expanded", "liability"))
# Each default, by code and name: set only to an account that is what it says (a chart that
# already uses 1300 for something else leaves Input VAT unset, for an Administrator to pick).
POSTING = {
    "payables_account_id": ("2000", "Accounts payable"),
    "input_tax_account_id": ("1300", "Input VAT"),
    "withholding_account_id": ("2300", "Withholding tax payable - expanded"),
}
STAFF, AUDITOR = "00000000-0000-4000-8000-00000000f002", "00000000-0000-4000-8000-00000000f003"
GRANTS = {
    STAFF: ("suppliers.view", "suppliers.manage", "bills.view", "bills.record"),
    AUDITOR: ("suppliers.view", "bills.view"),
}


def numbered(bind, table: str) -> None:
    """The record number (from 40000001): a sequence on Postgres; the app gives it on SQLite."""
    if bind.dialect.name == "postgresql":
        seq = f"{table}_no_seq"
        bind.execute(sa.text(f"create sequence if not exists {seq} start with {FIRST}"))
        bind.execute(sa.text(f"alter table {table} alter column no set default nextval('{seq}')"))
        bind.execute(sa.text(f"alter sequence {seq} owned by {table}.no"))
    op.create_index(f"{table}_no", table, ["no"], unique=True)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "parent_id" not in {c["name"] for c in inspector.get_columns("nbfi_accounts")}:
        # Added in place, never by rebuilding the table: on SQLite a rebuild drops the old
        # table, and everything pointing at an account (the default accounts, the expense
        # categories) would be emptied by its ON DELETE SET NULL. Found in testing, 2026-10-23.
        op.add_column("nbfi_accounts", sa.Column("parent_id", sa.String(36), nullable=True))
        if bind.dialect.name == "postgresql":
            op.create_foreign_key("nbfi_accounts_parent_id_fkey", "nbfi_accounts", "nbfi_accounts", ["parent_id"], ["id"], ondelete="SET NULL")

    if "nbfi_suppliers" not in tables:
        op.create_table(
            "nbfi_suppliers",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("no", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("tin", sa.String(11), nullable=True),
            sa.Column("branch_code", sa.String(5), nullable=True),
            sa.Column("address", sa.String(300), nullable=True),
            sa.Column("vat_registered", sa.Boolean(), nullable=False),
            sa.Column("withholding", sa.String(10), nullable=True),
            sa.Column("terms_days", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(254), nullable=True),
            sa.Column("phone", sa.String(40), nullable=True),
            sa.Column("bank_name", sa.String(80), nullable=True),
            sa.Column("bank_account_name", sa.String(120), nullable=True),
            sa.Column("bank_account_number", sa.String(40), nullable=True),
            sa.Column("notes", sa.String(500), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
        )
        numbered(bind, "nbfi_suppliers")

    if "nbfi_bills" not in tables:
        op.create_table(
            "nbfi_bills",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("no", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(10), nullable=False),
            sa.Column("supplier_id", sa.String(36), sa.ForeignKey("nbfi_suppliers.id"), nullable=False),
            sa.Column("bill_number", sa.String(60), nullable=False),
            sa.Column("bill_date", sa.Date(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=False),
            sa.Column("po_number", sa.String(60), nullable=True),
            sa.Column("dr_number", sa.String(60), nullable=True),
            sa.Column("checked_po", sa.Boolean(), nullable=False),
            sa.Column("checked_dr", sa.Boolean(), nullable=False),
            sa.Column("amounts_include_vat", sa.Boolean(), nullable=False),
            sa.Column("zoho_ref", sa.String(60), nullable=True),
            sa.Column("oojeema_ref", sa.String(60), nullable=True),
            sa.Column("notes", sa.String(500), nullable=True),
            sa.Column("lines", sa.JSON(), nullable=False),
            sa.Column("net_centavos", sa.Integer(), nullable=False),
            sa.Column("vat_centavos", sa.Integer(), nullable=False),
            sa.Column("withheld_centavos", sa.Integer(), nullable=False),
            sa.Column("total_centavos", sa.Integer(), nullable=False),
            sa.Column("payable_centavos", sa.Integer(), nullable=False),
            sa.Column("entry_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("recorded_by", sa.String(120), nullable=True),
            sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("voided_by", sa.String(120), nullable=True),
            sa.Column("void_reason", sa.String(300), nullable=True),
            sa.CheckConstraint("status IN ('draft', 'recorded', 'void')", name="bill_status"),
        )
        op.create_index("ix_nbfi_bills_status", "nbfi_bills", ["status"])
        op.create_index("ix_nbfi_bills_supplier_id", "nbfi_bills", ["supplier_id"])
        numbered(bind, "nbfi_bills")

    if "nbfi_bill_files" not in tables:
        op.create_table(
            "nbfi_bill_files",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("bill_id", sa.String(36), sa.ForeignKey("nbfi_bills.id", ondelete="CASCADE"), nullable=False),
            sa.Column("ref", sa.String(32), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("uploaded_by", sa.String(120), nullable=False),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_nbfi_bill_files_bill_id", "nbfi_bill_files", ["bill_id"])

    stamp = datetime.now(UTC)
    for code, name, type_ in NEW_ACCOUNTS:
        if bind.execute(sa.text("SELECT id FROM nbfi_accounts WHERE code = :c"), {"c": code}).scalar() is None:
            bind.execute(
                sa.text("INSERT INTO nbfi_accounts (id, code, name, type, description, is_active, created_at) VALUES (:id, :c, :n, :t, NULL, :a, :at)"),
                {"id": str(uuid.uuid4()), "c": code, "n": name, "t": type_, "a": True, "at": stamp},
            )
            if bind.dialect.name == "sqlite":  # Postgres numbers it by itself (migration 0009's sequence)
                bind.execute(sa.text("UPDATE nbfi_accounts SET no = (SELECT coalesce(max(no), :f - 1) + 1 FROM nbfi_accounts) WHERE code = :c AND no IS NULL"),
                             {"c": code, "f": FIRST})
    # Plain added columns: SQLite adds them in place (the foreign keys are the model's).
    have = {c["name"] for c in sa.inspect(bind).get_columns("nbfi_ledger_settings")}
    for column, (code, name) in POSTING.items():
        if column not in have:
            op.add_column("nbfi_ledger_settings", sa.Column(column, sa.String(36), nullable=True))
        account = bind.execute(sa.text("SELECT id FROM nbfi_accounts WHERE code = :c AND lower(name) = lower(:n) AND is_active"), {"c": code, "n": name}).scalar()
        if account:
            bind.execute(sa.text(f"UPDATE nbfi_ledger_settings SET {column} = :a WHERE id = 1 AND {column} IS NULL"), {"a": account})

    for role, permissions in GRANTS.items():
        if bind.execute(sa.text("SELECT id FROM nbfi_roles WHERE id = :r"), {"r": role}).scalar() is None:
            continue
        for p in permissions:
            if bind.execute(sa.text("SELECT 1 FROM nbfi_role_permissions WHERE role_id = :r AND permission = :p"), {"r": role, "p": p}).scalar() is None:
                bind.execute(sa.text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES (:r, :p)"), {"r": role, "p": p})


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission LIKE 'suppliers.%' OR permission LIKE 'bills.%'"))
    with op.batch_alter_table("nbfi_ledger_settings") as batch:
        for column in POSTING:
            batch.drop_column(column)
    op.drop_table("nbfi_bill_files")
    op.drop_table("nbfi_bills")
    op.drop_table("nbfi_suppliers")
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("nbfi_accounts_parent_id_fkey", "nbfi_accounts", type_="foreignkey")
    op.drop_column("nbfi_accounts", "parent_id")
