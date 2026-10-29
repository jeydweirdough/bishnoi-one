"""Banks, payments and equity (feature plan step 16, 2026-10-29).

- nbfi_bank_accounts: the company's bank accounts and e-wallets (BDO, BPI… GCash, Maya), each with its ledger
  account; invoice payments name where the money went, with a check's details (16a).
- nbfi_tax_profile.rounding: VAT worked out per line (as before) or once per invoice (16b).
- nbfi_exchange_rates, and on bills their currency and the rate on the bill's day; on vouchers the rate on the
  day paid and the exchange difference (16c).
- nbfi_ledger_settings: capital, drawings, retained earnings, exchange gain and loss accounts; the books locked
  up to a day (16d, 16e). nbfi_year_closings: each closed fiscal year and its closing entry (16d).

Added in place: on SQLite a table rebuild drops what points at it.

Revision ID: 0028
Revises: 0027
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

ADD = (
    ("nbfi_invoice_payments", "bank_account_id", sa.String(36), None),
    ("nbfi_invoice_payments", "check_number", sa.String(40), None),
    ("nbfi_invoice_payments", "check_bank", sa.String(60), None),
    ("nbfi_invoice_payments", "check_date", sa.Date(), None),
    ("nbfi_tax_profile", "rounding", sa.String(8), "line"),
    ("nbfi_bills", "currency", sa.String(3), "PHP"),
    ("nbfi_bills", "rate_e4", sa.Integer(), None),
    ("nbfi_bills", "foreign_total", sa.Integer(), None),
    ("nbfi_bills", "foreign_payable", sa.Integer(), None),
    ("nbfi_payment_vouchers", "rate_e4", sa.Integer(), None),
    ("nbfi_payment_vouchers", "exchange_centavos", sa.Integer(), None),
    ("nbfi_payment_vouchers", "bank_account_id", sa.String(36), None),
    ("nbfi_ledger_settings", "capital_account_id", sa.String(36), None),
    ("nbfi_ledger_settings", "drawings_account_id", sa.String(36), None),
    ("nbfi_ledger_settings", "retained_earnings_account_id", sa.String(36), None),
    ("nbfi_ledger_settings", "fx_gain_account_id", sa.String(36), None),
    ("nbfi_ledger_settings", "fx_loss_account_id", sa.String(36), None),
    ("nbfi_ledger_settings", "locked_until", sa.Date(), None),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table, name, kind, default in ADD:
        if name not in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
            op.add_column(table, sa.Column(name, kind, nullable=default is None, **({"server_default": default} if default is not None else {})))
    tables = set(sa.inspect(bind).get_table_names())
    if "nbfi_bank_accounts" not in tables:
        op.create_table(
            "nbfi_bank_accounts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("kind", sa.String(8), nullable=False),
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("account_name", sa.String(160)),
            sa.Column("account_number", sa.String(40)),
            sa.Column("currency", sa.String(3), nullable=False, server_default="PHP"),
            sa.Column("account_id", sa.String(36), sa.ForeignKey("nbfi_accounts.id"), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("kind IN ('bank', 'ewallet', 'cash')", name="bank_account_kind"),
        )
    if "nbfi_exchange_rates" not in tables:
        op.create_table(
            "nbfi_exchange_rates",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("on", sa.Date(), nullable=False),
            sa.Column("rate_e4", sa.Integer(), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("currency", "on", name="exchange_rate_day"),
        )
    if "nbfi_year_closings" not in tables:
        op.create_table(
            "nbfi_year_closings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("year_end", sa.Date(), nullable=False, unique=True),
            sa.Column("entry_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL")),
            sa.Column("net_income_centavos", sa.Integer(), nullable=False),
            sa.Column("closed_by", sa.String(120), nullable=False),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("nbfi_year_closings")
    op.drop_table("nbfi_exchange_rates")
    op.drop_table("nbfi_bank_accounts")
    for table, name, _, _ in reversed(ADD):
        with op.batch_alter_table(table) as batch:
            batch.drop_column(name)
