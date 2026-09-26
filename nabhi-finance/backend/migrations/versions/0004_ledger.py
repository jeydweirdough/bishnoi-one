"""The ledger: a chart of accounts, a double-entry journal, and which
accounts the fund steps post to.

- nbfi_accounts: the chart, with a starting set Finance changes as it likes.
- nbfi_ledger_settings: the posting accounts (advances, due to employees,
  and where cash, bank, e-wallet and check money moves).
- nbfi_journal_entries, nbfi_journal_lines: every entry, debits = credits.
- nbfi_expense_categories.parent_id, account_id: sub-categories, and each
  category's expense account.

Each step only if it isn't done yet.

Revision ID: 0004
Revises: 0003
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# A small starting chart, numbered the usual way (1 assets, 2 liabilities,
# 3 equity, 4 income, 6 expenses). Finance adds, renames and switches off.
ACCOUNTS = (
    ("1000", "Cash on hand", "asset"),
    ("1010", "Cash in bank", "asset"),
    ("1020", "E-wallet (GCash, Maya)", "asset"),
    ("1200", "Advances to employees", "asset"),
    ("2000", "Accounts payable", "liability"),
    ("2100", "Due to employees", "liability"),
    ("3000", "Owner's equity", "equity"),
    ("4000", "Sales", "income"),
    ("6100", "Food", "expense"),
    ("6200", "Transportation", "expense"),
    ("6300", "Fuel, parking & tolls", "expense"),
    ("6400", "Lodging", "expense"),
    ("6500", "Supplies & materials", "expense"),
    ("6900", "Other expenses", "expense"),
)
# The fund categories 0003 made: which account each posts to, and the
# sub-categories that start under it.
CATEGORY_ACCOUNTS = {
    "Meals & representation": ("6100", "Food", ("Dining", "Breakfast", "Snacks & coffee")),
    "Transportation": ("6200", None, ("Taxi & ride-hailing", "Fares", "Airfare")),
    "Fuel, parking & tolls": ("6300", None, ("Fuel", "Parking", "Tolls")),
    "Lodging": ("6400", None, ()),
    "Supplies & materials": ("6500", None, ("Samples", "Printing")),
    "Personal": ("6900", None, ()),
}
POSTING = {
    "advances_account_id": "1200",
    "due_to_employees_account_id": "2100",
    "cash_account_id": "1000",
    "bank_account_id": "1010",
    "ewallet_account_id": "1020",
    "check_account_id": "1010",
}


def upgrade() -> None:
    db = op.get_bind()
    inspector = sa.inspect(db)
    tables = set(inspector.get_table_names())
    now = sa.DateTime(timezone=True)
    stamp = datetime.now(UTC)

    if "nbfi_accounts" not in tables:
        accounts = op.create_table(
            "nbfi_accounts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(20), nullable=False, unique=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("type", sa.String(10), nullable=False),
            sa.Column("description", sa.String(300), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", now, nullable=False),
            sa.CheckConstraint("type IN ('asset', 'liability', 'equity', 'income', 'expense')", name="account_type"),
        )
        op.bulk_insert(accounts, [
            {"id": str(uuid.uuid4()), "code": c, "name": n, "type": t, "description": None, "is_active": True, "created_at": stamp}
            for c, n, t in ACCOUNTS
        ])
    account = lambda code: db.execute(sa.text("SELECT id FROM nbfi_accounts WHERE code = :c"), {"c": code}).scalar()  # noqa: E731

    if "nbfi_ledger_settings" not in tables:
        op.create_table(
            "nbfi_ledger_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            *[sa.Column(k, sa.String(36), sa.ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), nullable=True) for k in POSTING],
            sa.CheckConstraint("id = 1", name="one_ledger_settings"),
        )
        db.execute(
            sa.text(f"INSERT INTO nbfi_ledger_settings (id, {', '.join(POSTING)}) VALUES (1, {', '.join(':' + k for k in POSTING)})"),
            {k: account(code) for k, code in POSTING.items()},
        )

    if "nbfi_journal_entries" not in tables:
        op.create_table(
            "nbfi_journal_entries",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("number", sa.String(20), nullable=False, unique=True),
            sa.Column("entry_date", sa.Date(), nullable=False, index=True),
            sa.Column("memo", sa.String(300), nullable=False),
            sa.Column("reference", sa.String(80), nullable=True),
            sa.Column("source", sa.String(10), nullable=False),
            sa.Column("fund_request_id", sa.String(36), sa.ForeignKey("nbfi_fund_requests.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("reverses_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reversed_by_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("posted_by", sa.String(120), nullable=False),
            sa.Column("created_at", now, nullable=False),
        )
    if "nbfi_journal_lines" not in tables:
        op.create_table(
            "nbfi_journal_lines",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("entry_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("account_id", sa.String(36), sa.ForeignKey("nbfi_accounts.id"), nullable=False, index=True),
            sa.Column("debit_centavos", sa.Integer(), nullable=False),
            sa.Column("credit_centavos", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(200), nullable=True),
            sa.CheckConstraint(
                "debit_centavos >= 0 AND credit_centavos >= 0 AND (debit_centavos = 0) <> (credit_centavos = 0)", name="one_side"
            ),
        )

    have = {c["name"] for c in inspector.get_columns("nbfi_expense_categories")}
    with op.batch_alter_table("nbfi_expense_categories") as batch:
        if "parent_id" not in have:
            batch.add_column(sa.Column("parent_id", sa.String(36), nullable=True))
            batch.create_foreign_key("fk_category_parent", "nbfi_expense_categories", ["parent_id"], ["id"], ondelete="CASCADE")
        if "account_id" not in have:
            batch.add_column(sa.Column("account_id", sa.String(36), nullable=True))
            batch.create_foreign_key("fk_category_account", "nbfi_accounts", ["account_id"], ["id"], ondelete="SET NULL")
    if "account_id" not in have:
        for name, (code, rename, subs) in CATEGORY_ACCOUNTS.items():
            top = db.execute(sa.text("SELECT id FROM nbfi_expense_categories WHERE name = :n AND parent_id IS NULL"), {"n": name}).scalar()
            if not top:
                continue
            db.execute(sa.text("UPDATE nbfi_expense_categories SET account_id = :a WHERE id = :id"), {"a": account(code), "id": top})
            if rename:
                db.execute(sa.text("UPDATE nbfi_expense_categories SET name = :r WHERE id = :id"), {"r": rename, "id": top})
            for i, sub in enumerate(subs):
                db.execute(
                    sa.text(
                        "INSERT INTO nbfi_expense_categories (id, name, parent_id, account_id, reimbursable, description, is_active, sort_order) "
                        "VALUES (:id, :n, :p, NULL, true, NULL, true, :i)"
                    ),
                    {"id": str(uuid.uuid4()), "n": sub, "p": top, "i": i},
                )


def downgrade() -> None:
    with op.batch_alter_table("nbfi_expense_categories") as batch:
        batch.drop_constraint("fk_category_account", type_="foreignkey")
        batch.drop_constraint("fk_category_parent", type_="foreignkey")
        batch.drop_column("account_id")
        batch.drop_column("parent_id")
    for table in ("nbfi_journal_lines", "nbfi_journal_entries", "nbfi_ledger_settings", "nbfi_accounts"):
        op.drop_table(table)
