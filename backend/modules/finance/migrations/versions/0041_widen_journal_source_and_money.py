"""Widen nbfi_journal_entries.source to String(24) and money centavos columns to BigInteger on PostgreSQL."""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

MONEY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("nbfi_sales_orders", "total_centavos"),
    ("nbfi_sales_orders", "tax_centavos"),
    ("nbfi_year_closings", "net_income_centavos"),
    ("nbfi_fixed_assets", "cost_centavos"),
    ("nbfi_fixed_assets", "salvage_centavos"),
    ("nbfi_fixed_assets", "accumulated_centavos"),
    ("nbfi_journal_lines", "debit_centavos"),
    ("nbfi_journal_lines", "credit_centavos"),
    ("nbfi_fund_requests", "requested_centavos"),
    ("nbfi_fund_requests", "approved_centavos"),
    ("nbfi_fund_requests", "released_centavos"),
    ("nbfi_fund_requests", "covered_centavos"),
    ("nbfi_fund_requests", "return_due_centavos"),
    ("nbfi_fund_requests", "returned_centavos"),
    ("nbfi_fund_requests", "reimburse_due_centavos"),
    ("nbfi_fund_requests", "reimbursed_centavos"),
    ("nbfi_fund_expenses", "amount_centavos"),
    ("nbfi_fund_events", "amount_centavos"),
    ("nbfi_invoices", "cost_centavos"),
    ("nbfi_invoices", "total_centavos"),
    ("nbfi_invoices", "tax_centavos"),
    ("nbfi_invoices", "paid_centavos"),
    ("nbfi_invoice_payments", "amount_centavos"),
    ("nbfi_invoice_payments", "cwt_centavos"),
    ("nbfi_bills", "net_centavos"),
    ("nbfi_bills", "vat_centavos"),
    ("nbfi_bills", "withheld_centavos"),
    ("nbfi_bills", "total_centavos"),
    ("nbfi_bills", "payable_centavos"),
    ("nbfi_bills", "paid_centavos"),
    ("nbfi_payment_vouchers", "total_centavos"),
    ("nbfi_voucher_lines", "amount_centavos"),
    ("nbfi_bank_reconciliations", "statement_balance_centavos"),
    ("nbfi_bank_reconciliations", "opening_balance_centavos"),
)


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite stores arbitrary-length text and 64-bit signed integers natively;
        # never batch-rebuild referenced tables on SQLite.
        return
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "nbfi_journal_entries" in tables:
        cols = {c["name"]: c for c in inspector.get_columns("nbfi_journal_entries")}
        if "source" in cols:
            op.alter_column(
                "nbfi_journal_entries",
                "source",
                existing_type=sa.String(length=10),
                type_=sa.String(length=24),
                existing_nullable=cols["source"].get("nullable", False),
            )
    for table, col in MONEY_COLUMNS:
        if table not in tables:
            continue
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        if col not in cols:
            continue
        op.alter_column(
            table,
            col,
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=cols[col].get("nullable", False),
        )


def downgrade():
    # Widening column types is intentionally non-destructive; do not truncate live data on downgrade.
    pass
