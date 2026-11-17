"""Bills in foreign currencies removed (owner's decision, 2026-11-17): bills are pesos only.

Drops what step 16c added for USD bills and exchange gains or losses:

- nbfi_exchange_rates (the day rates), and recycle-bin entries of kind "exchange-rates";
- nbfi_bills.currency, rate_e4, foreign_total, foreign_payable;
- nbfi_payment_vouchers.rate_e4, exchange_centavos;
- nbfi_ledger_settings.fx_gain_account_id, fx_loss_account_id (the default accounts).

It refuses to run (and changes nothing) while any bill is in a currency other than PHP or carries a rate, or any
payment voucher carries a rate or an exchange gain or loss, including ones in the recycle bin: dropping the
columns would leave such money in pesos it was never in. Settle those by hand first.

In place only: ALTER TABLE ... DROP COLUMN on each dialect (SQLite 3.35+), never a batch rebuild, because a
SQLite batch rebuild of nbfi_bills / nbfi_payment_vouchers drops the rows pointing at them (see 0027).

Revision ID: 0036
Revises: 0035
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

COLUMNS = {
    "nbfi_bills": ("currency", "rate_e4", "foreign_total", "foreign_payable"),
    "nbfi_payment_vouchers": ("rate_e4", "exchange_centavos"),
    "nbfi_ledger_settings": ("fx_gain_account_id", "fx_loss_account_id"),
}


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _foreign(table: str, row: dict) -> bool:
    if table == "nbfi_bills":
        return (row.get("currency") or "PHP") != "PHP" or row.get("rate_e4") is not None
    if table == "nbfi_payment_vouchers":
        return bool(row.get("exchange_centavos")) or row.get("rate_e4") is not None
    return False


def _refuse_foreign_money(bind, tables: set[str]) -> None:
    problems = []
    if "nbfi_bills" in tables:
        have = _columns(bind, "nbfi_bills")
        checks = []
        if "currency" in have:
            checks.append("COALESCE(currency, 'PHP') <> 'PHP'")
        if "rate_e4" in have:
            checks.append("rate_e4 IS NOT NULL")
        if checks:
            found = bind.execute(sa.text(f"SELECT no, bill_number FROM nbfi_bills WHERE {' OR '.join(checks)}")).all()
            problems += [f"bill {no} ({number})" for no, number in found]
    if "nbfi_payment_vouchers" in tables:
        have = _columns(bind, "nbfi_payment_vouchers")
        checks = []
        if "exchange_centavos" in have:
            checks.append("COALESCE(exchange_centavos, 0) <> 0")
        if "rate_e4" in have:
            checks.append("rate_e4 IS NOT NULL")
        if checks:
            found = bind.execute(sa.text(f"SELECT number FROM nbfi_payment_vouchers WHERE {' OR '.join(checks)}")).all()
            problems += [f"payment voucher {number}" for (number,) in found]
    if "nbfi_recycle_bin" in tables:
        for entry_id, rows in bind.execute(sa.text("SELECT id, rows FROM nbfi_recycle_bin")).all():
            items = json.loads(rows) if isinstance(rows, str) else rows
            if any(_foreign(i.get("t"), i.get("d") or {}) for i in items or []):
                problems.append(f"recycle-bin entry {entry_id}")
    if problems:
        raise RuntimeError(
            "Migration 0036 removes foreign-currency bills, but these still hold a foreign currency, an exchange rate "
            f"or an exchange gain or loss: {', '.join(problems[:20])}{' and more' if len(problems) > 20 else ''}. "
            "Nothing was changed. Settle them in pesos by hand (or keep the previous release) before upgrading."
        )


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    _refuse_foreign_money(bind, tables)
    if "nbfi_recycle_bin" in tables:
        bind.execute(sa.text("DELETE FROM nbfi_recycle_bin WHERE kind = 'exchange-rates'"))
    if "nbfi_exchange_rates" in tables:
        op.drop_table("nbfi_exchange_rates")
    for table, names in COLUMNS.items():
        if table not in tables:
            continue
        have = _columns(bind, table)
        for name in names:
            if name in have:
                # Plain ALTER TABLE on every dialect: no batch rebuild (it would lose rows pointing at the table).
                bind.execute(sa.text(f'ALTER TABLE "{table}" DROP COLUMN "{name}"'))


def downgrade() -> None:
    raise NotImplementedError("0036 removed foreign-currency bills and their columns (2026-11-17); restore from the copy made before it.")
