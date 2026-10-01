"""Sales invoices, numbered from the BIR's authority (benchmarks decision D4).

- nbfi_invoice_series: each run of numbers the BIR authorized (its ATP), used
  in order and never past the last;
- nbfi_invoices: a draft until it's issued; issued, it keeps its number and
  its amounts, and posts to the ledger;
- three more default accounts, where an issued invoice posts: Accounts
  receivable (1100, added if missing), Sales (4000) and Output VAT payable
  (2200, added if missing);
- the invoices permissions, given to the roles that already exist: Finance
  Staff make and issue invoices, the Auditor sees them.

Revision ID: 0007
Revises: 0006
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

STAFF_ID = "00000000-0000-4000-8000-00000000f002"
AUDITOR_ID = "00000000-0000-4000-8000-00000000f003"
GRANTS = {STAFF_ID: ["invoices.view", "invoices.create", "invoices.issue"], AUDITOR_ID: ["invoices.view"]}
NEW_ACCOUNTS = (("1100", "Accounts receivable", "asset"), ("2200", "Output VAT payable", "liability"))
POSTING = {"receivables_account_id": "1100", "sales_account_id": "4000", "output_tax_account_id": "2200"}


def upgrade() -> None:
    db = op.get_bind()
    inspector = sa.inspect(db)
    tables = set(inspector.get_table_names())

    if "nbfi_invoice_series" not in tables:
        op.create_table(
            "nbfi_invoice_series",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("prefix", sa.String(10), nullable=False, server_default=""),
            sa.Column("digits", sa.Integer(), nullable=False, server_default="6"),
            sa.Column("first_number", sa.Integer(), nullable=False),
            sa.Column("last_number", sa.Integer(), nullable=False),
            sa.Column("next_number", sa.Integer(), nullable=False),
            sa.Column("atp_number", sa.String(40), nullable=False),
            sa.Column("atp_date", sa.Date(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("first_number <= last_number", name="series_range"),
        )
    if "nbfi_invoices" not in tables:
        op.create_table(
            "nbfi_invoices",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("status", sa.String(10), nullable=False, index=True),
            sa.Column("series_id", sa.String(36), sa.ForeignKey("nbfi_invoice_series.id"), nullable=True),
            sa.Column("number", sa.String(30), nullable=True, unique=True),
            sa.Column("customer_id", sa.String(36), nullable=True, index=True),
            sa.Column("customer_name", sa.String(200), nullable=False),
            sa.Column("customer_tin", sa.String(20), nullable=True),
            sa.Column("customer_address", sa.String(300), nullable=True),
            sa.Column("treatment", sa.String(20), nullable=False, server_default="regular"),
            sa.Column("buyer_id_number", sa.String(40), nullable=True),
            sa.Column("invoice_date", sa.Date(), nullable=False),
            sa.Column("terms_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("reference", sa.String(80), nullable=True),
            sa.Column("notes", sa.String(500), nullable=True),
            sa.Column("prices_include_tax", sa.Boolean(), nullable=True),
            sa.Column("lines", sa.JSON(), nullable=False),
            sa.Column("computed", sa.JSON(), nullable=True),
            sa.Column("total_centavos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tax_centavos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("paid_centavos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("entry_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("issued_by", sa.String(120), nullable=True),
            sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("voided_by", sa.String(120), nullable=True),
            sa.Column("void_reason", sa.String(300), nullable=True),
            sa.CheckConstraint("status IN ('draft', 'issued', 'void')", name="invoice_status"),
        )

    stamp = datetime.now(UTC)
    for code, name, type_ in NEW_ACCOUNTS:
        if db.execute(sa.text("SELECT id FROM nbfi_accounts WHERE code = :c"), {"c": code}).scalar() is None:
            db.execute(
                sa.text("INSERT INTO nbfi_accounts (id, code, name, type, description, is_active, created_at) VALUES (:id, :c, :n, :t, NULL, :a, :at)"),
                {"id": str(uuid.uuid4()), "c": code, "n": name, "t": type_, "a": True, "at": stamp},
            )
    # Plain added columns: SQLite adds them in place (the foreign keys are the model's).
    have = {c["name"] for c in inspector.get_columns("nbfi_ledger_settings")}
    for column, code in POSTING.items():
        if column not in have:
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
    op.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission LIKE 'invoices.%'"))
    with op.batch_alter_table("nbfi_ledger_settings") as batch:
        for column in POSTING:
            batch.drop_column(column)
    op.drop_table("nbfi_invoices")
    op.drop_table("nbfi_invoice_series")
