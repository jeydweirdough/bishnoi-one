"""Phase 1 safeguards: Postgres column widths/sizes, Year-End Close & P&L, 2MG bulk scope approval, and safe account deactivation."""
from datetime import date

from sqlalchemy import BigInteger, select

from modules.finance import bir_reports
from modules.finance.ledger import Leg, post
from modules.finance.models import Account, CompanyScopeReview, JournalEntry, LedgerSettings, Supplier
from .test_tax_api import app, client, ana


def _approve_all_accounts(app):
    with app.state.sessions() as db:
        for a in db.scalars(select(Account)):
            db.merge(CompanyScopeReview(subject_kind="account", subject_id=a.id, scope="2mg", evidence={"source": "test"}, reviewed_by="TEST"))
        db.commit()


def test_journal_source_widened_and_money_columns_use_biginteger():
    assert JournalEntry.__table__.c.source.type.length >= 24
    for table in (
        "nbfi_sales_orders",
        "nbfi_year_closings",
        "nbfi_fixed_assets",
        "nbfi_journal_lines",
        "nbfi_fund_requests",
        "nbfi_fund_expenses",
        "nbfi_fund_events",
        "nbfi_invoices",
        "nbfi_invoice_payments",
        "nbfi_bills",
        "nbfi_payment_vouchers",
        "nbfi_voucher_lines",
        "nbfi_bank_reconciliations",
    ):
        tbl = JournalEntry.metadata.tables[table]
        for col in tbl.columns:
            if col.name.endswith("_centavos"):
                assert isinstance(col.type, BigInteger), f"{table}.{col.name} should be BigInteger"


def test_bulk_approve_accounts_and_suppliers_for_2mg(app, client, ana):
    # Bulk import an account (starts outside 2mg)
    imp = client.post(
        "/finance/ledger/accounts/import",
        headers=ana,
        json={"accounts": [{"code": "6991-000", "name": "Test Imported Expense", "type": "expense"}]},
    )
    assert imp.status_code == 201, imp.text

    # Not in 2mg yet, visible in history
    active_codes = {a["code"] for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"]}
    assert "6991-000" not in active_codes
    history_items = client.get("/finance/ledger/accounts?company_use=history", headers=ana).json()["items"]
    imported = next(a for a in history_items if a["code"] == "6991-000")

    # Approve for 2MG via new endpoint
    ok = client.post(
        "/finance/ledger/accounts/company-scope/approve",
        headers=ana,
        json={"accountIds": [imported["id"]], "reason": "Verified 2MG chart"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["approved"] == 1
    active_codes_after = {a["code"] for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"]}
    assert "6991-000" in active_codes_after

    # Create a supplier without 2mg review (like bulk import) on books that review suppliers, and approve it
    with app.state.sessions() as db:
        reviewed = Supplier(name="Reviewed 2MG Vendor", created_by="TEST", is_active=True)
        db.add(reviewed); db.flush()
        db.add(CompanyScopeReview(subject_kind="supplier", subject_id=reviewed.id, scope="2mg", evidence={"source": "fictional test"}, reviewed_by="TEST"))
        s = Supplier(name="Imported 2MG Vendor", created_by="TEST", is_active=True)
        db.add(s)
        db.commit()
        sid = s.id
    assert all(x["id"] != sid for x in client.get("/finance/suppliers", headers=ana).json()["items"])

    ok_sup = client.post(
        "/finance/suppliers/company-scope/approve",
        headers=ana,
        json={"supplierIds": [sid], "reason": "Verified 2MG vendor"},
    )
    assert ok_sup.status_code == 200, ok_sup.text
    assert ok_sup.json()["approved"] == 1
    assert any(x["id"] == sid for x in client.get("/finance/suppliers", headers=ana).json()["items"])


def test_account_deactivation_blocked_when_linked_to_defaults_or_waiting_journal(app, client, ana):
    _approve_all_accounts(app)
    with app.state.sessions() as db:
        s = db.get(LedgerSettings, 1)
        cash_id = s.cash_account_id
        cash = db.get(Account, cash_id)
        payload = {"code": cash.code, "name": cash.name, "type": cash.type, "isActive": False}

    blocked = client.put(f"/finance/ledger/accounts/{cash_id}", headers=ana, json=payload)
    assert blocked.status_code == 422
    assert "default posting accounts" in blocked.text


def test_year_end_close_allows_deactivated_nominal_and_preserves_income_statement(app, client, ana):
    _approve_all_accounts(app)
    # Create an income, an expense, and retained earnings account
    inc = client.post("/finance/ledger/accounts", headers=ana, json={"code": "4199", "name": "Close Test Sales", "type": "income"}).json()
    exp = client.post("/finance/ledger/accounts", headers=ana, json={"code": "6199", "name": "Close Test Expense", "type": "expense"}).json()
    ret = client.post("/finance/ledger/accounts", headers=ana, json={"code": "3199", "name": "Close Test Retained", "type": "equity"}).json()
    cap = client.post("/finance/ledger/accounts", headers=ana, json={"code": "3198", "name": "Close Test Capital", "type": "equity"}).json()
    drw = client.post("/finance/ledger/accounts", headers=ana, json={"code": "3197", "name": "Close Test Drawings", "type": "equity"}).json()

    with app.state.sessions() as db:
        s = db.get(LedgerSettings, 1)
        cash = db.get(Account, s.cash_account_id)
        inc_a = db.get(Account, inc["id"])
        exp_a = db.get(Account, exp["id"])
        s.retained_earnings_account_id = ret["id"]
        s.capital_account_id = cap["id"]
        s.drawings_account_id = drw["id"]
        # Post 2025 activity: 100,000 sales, 40,000 expense -> 60,000 net income
        post(db, date(2025, 6, 15), "2025 sales", [Leg(cash, debit=100_000_00), Leg(inc_a, credit=100_000_00)], "TEST")
        post(db, date(2025, 7, 10), "2025 expense", [Leg(exp_a, debit=40_000_00), Leg(cash, credit=40_000_00)], "TEST")
        # Deactivate the historical expense account BEFORE closing 2025
        exp_a.is_active = False
        db.commit()

    # Closing 2025 must succeed even though exp_a is now inactive
    closed = client.post("/finance/closing", headers=ana, json={"yearEnd": "2025-12-31", "lock": False})
    assert closed.status_code == 200, closed.text
    assert closed.json()["netIncomeCentavos"] == 60_000_00

    # Income Statement for 2025 must still report 100k income, 40k expense, 60k net (NOT 0!)
    with app.state.sessions() as db:
        is_2025 = bir_reports.income_statement(db, date(2025, 1, 1), date(2025, 12, 31))
        assert is_2025["totals"]["incomeCentavos"] == 100_000_00
        assert is_2025["totals"]["expensesCentavos"] == 40_000_00
        assert is_2025["totals"]["netCentavos"] == 60_000_00

        # Balance Sheet as of 2025-12-31 must remain balanced with net income closed into Retained Earnings
        bs_2025 = bir_reports.balance_sheet(db, date(2025, 12, 31))
        assert bs_2025["totals"]["balanced"] is True
