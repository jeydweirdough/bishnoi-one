"""Payment vouchers: paying suppliers' recorded bills.

- nbfi_payment_vouchers: one voucher for one supplier: status, how and from which account
  it's paid, the Hub's number (PV-YYYYMM-NNNN), Oojeema's PV number and Zoho's reference,
  who prepared, checked, approved and released it, the bank reference or check number.
- nbfi_voucher_lines (which bill, how much), nbfi_voucher_events (submitted, checked,
  returned with the reason, approved, released, cancelled, voided), nbfi_voucher_files
  (deposit slip, check photo; the files themselves in nbfi_stored_files).
- nbfi_bills: what's been paid on each, and the payables account it posted to when
  recorded (filled in for bills already recorded, from their own journal entry).
- The starting roles: Finance Staff prepares vouchers; the Auditor sees them. Other roles
  are ticked on the Roles screen.

Added in place, never by rebuilding a table (see 0017). Decided 2026-10-23 (Plans/Plan -
Payment vouchers). Main's latest migration was 0012 when this was written (checked
right before).

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

FIRST = 40000001
STAFF, AUDITOR = "00000000-0000-4000-8000-00000000f002", "00000000-0000-4000-8000-00000000f003"
GRANTS = {STAFF: ("vouchers.view", "vouchers.prepare"), AUDITOR: ("vouchers.view",)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    postgres = bind.dialect.name == "postgresql"

    have = {c["name"] for c in inspector.get_columns("nbfi_bills")}
    if "paid_centavos" not in have:
        op.add_column("nbfi_bills", sa.Column("paid_centavos", sa.Integer(), nullable=False, server_default="0"))
    if "payables_account_id" not in have:
        op.add_column("nbfi_bills", sa.Column("payables_account_id", sa.String(36), nullable=True))
        if postgres:
            op.create_foreign_key("nbfi_bills_payables_account_id_fkey", "nbfi_bills", "nbfi_accounts", ["payables_account_id"], ["id"], ondelete="SET NULL")
        # Bills already recorded: the account their entry credited with what's owed the supplier.
        rows = bind.execute(sa.text("SELECT id, entry_id, payable_centavos FROM nbfi_bills WHERE status = 'recorded' AND entry_id IS NOT NULL")).all()
        for bill_id, entry_id, payable in rows:
            account = bind.execute(
                sa.text("SELECT account_id FROM nbfi_journal_lines WHERE entry_id = :e AND credit_centavos = :p ORDER BY position LIMIT 1"),
                {"e": entry_id, "p": payable},
            ).scalar()
            if account:
                bind.execute(sa.text("UPDATE nbfi_bills SET payables_account_id = :a WHERE id = :b"), {"a": account, "b": bill_id})

    if "nbfi_payment_vouchers" not in tables:
        op.create_table(
            "nbfi_payment_vouchers",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("no", sa.Integer(), nullable=True),
            sa.Column("number", sa.String(20), nullable=False, unique=True),
            sa.Column("status", sa.String(12), nullable=False),
            sa.Column("supplier_id", sa.String(36), sa.ForeignKey("nbfi_suppliers.id"), nullable=False),
            sa.Column("method", sa.String(10), nullable=False),
            sa.Column("paid_from_id", sa.String(36), sa.ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("total_centavos", sa.Integer(), nullable=False),
            sa.Column("oojeema_ref", sa.String(60), nullable=True),
            sa.Column("zoho_ref", sa.String(60), nullable=True),
            sa.Column("notes", sa.String(500), nullable=True),
            sa.Column("prepared_by", sa.String(120), nullable=False),
            sa.Column("prepared_by_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("checked_by", sa.String(120), nullable=True),
            sa.Column("checked_by_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("approved_by", sa.String(120), nullable=True),
            sa.Column("approved_by_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("released_by", sa.String(120), nullable=True),
            sa.Column("released_by_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("paid_on", sa.Date(), nullable=True),
            sa.Column("bank_reference", sa.String(80), nullable=True),
            sa.Column("check_number", sa.String(40), nullable=True),
            sa.Column("check_date", sa.Date(), nullable=True),
            sa.Column("entry_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status IN ('draft', 'returned', 'to_check', 'to_approve', 'to_release', 'released', 'cancelled', 'void')", name="voucher_status"),
        )
        op.create_index("ix_nbfi_payment_vouchers_status", "nbfi_payment_vouchers", ["status"])
        op.create_index("ix_nbfi_payment_vouchers_supplier_id", "nbfi_payment_vouchers", ["supplier_id"])
        if postgres:
            seq = "nbfi_payment_vouchers_no_seq"
            bind.execute(sa.text(f"create sequence if not exists {seq} start with {FIRST}"))
            bind.execute(sa.text(f"alter table nbfi_payment_vouchers alter column no set default nextval('{seq}')"))
            bind.execute(sa.text(f"alter sequence {seq} owned by nbfi_payment_vouchers.no"))
        op.create_index("nbfi_payment_vouchers_no", "nbfi_payment_vouchers", ["no"], unique=True)

    if "nbfi_voucher_lines" not in tables:
        op.create_table(
            "nbfi_voucher_lines",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("voucher_id", sa.String(36), sa.ForeignKey("nbfi_payment_vouchers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("bill_id", sa.String(36), sa.ForeignKey("nbfi_bills.id"), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("amount_centavos", sa.Integer(), nullable=False),
        )
        op.create_index("ix_nbfi_voucher_lines_voucher_id", "nbfi_voucher_lines", ["voucher_id"])
        op.create_index("ix_nbfi_voucher_lines_bill_id", "nbfi_voucher_lines", ["bill_id"])

    if "nbfi_voucher_events" not in tables:
        op.create_table(
            "nbfi_voucher_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("voucher_id", sa.String(36), sa.ForeignKey("nbfi_payment_vouchers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("who", sa.String(120), nullable=False),
            sa.Column("who_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("text", sa.String(300), nullable=True),
        )
        op.create_index("ix_nbfi_voucher_events_voucher_id", "nbfi_voucher_events", ["voucher_id"])

    if "nbfi_voucher_files" not in tables:
        op.create_table(
            "nbfi_voucher_files",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("voucher_id", sa.String(36), sa.ForeignKey("nbfi_payment_vouchers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("ref", sa.String(32), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("uploaded_by", sa.String(120), nullable=False),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_nbfi_voucher_files_voucher_id", "nbfi_voucher_files", ["voucher_id"])

    for role, permissions in GRANTS.items():
        if bind.execute(sa.text("SELECT id FROM nbfi_roles WHERE id = :r"), {"r": role}).scalar() is None:
            continue
        for p in permissions:
            if bind.execute(sa.text("SELECT 1 FROM nbfi_role_permissions WHERE role_id = :r AND permission = :p"), {"r": role, "p": p}).scalar() is None:
                bind.execute(sa.text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES (:r, :p)"), {"r": role, "p": p})


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission LIKE 'vouchers.%'"))
    op.drop_table("nbfi_voucher_files")
    op.drop_table("nbfi_voucher_events")
    op.drop_table("nbfi_voucher_lines")
    op.drop_table("nbfi_payment_vouchers")
    if bind.dialect.name == "postgresql":
        op.drop_constraint("nbfi_bills_payables_account_id_fkey", "nbfi_bills", type_="foreignkey")
    op.drop_column("nbfi_bills", "payables_account_id")
    op.drop_column("nbfi_bills", "paid_centavos")
