"""Banks, payments and equity (feature plan step 16): bank accounts and channels, VAT rounding per invoice, USD
bills paid at the day's rate, owner's equity and year-end closing, and the period lock."""

from datetime import date, timedelta

from sqlalchemy import select

from app.models import JournalEntry, JournalLine
from .test_invoices import TODAY, draft, issued, ready
from .test_tax_api import REGISTRATION, ana, app, client  # noqa: F401 (fixtures)


def account(client, ana, code, name, kind):  # noqa: F811
    r = client.post("/finance/ledger/accounts", json={"code": code, "name": name, "type": kind}, headers=ana)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def cash_in_bank(client, ana):  # noqa: F811
    return next(a["id"] for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"] if a["code"] == "1010")


def a_bank(client, ana, provider="bdo", name="BDO Savings 1234"):  # noqa: F811
    r = client.post("/finance/bank-accounts", json={"provider": provider, "name": name, "accountNumber": "001234567890", "accountId": cash_in_bank(client, ana), "isDefault": True}, headers=ana)
    assert r.status_code == 201, r.text
    return r.json()


def test_bank_accounts_and_a_payment_into_one(client, ana):  # noqa: F811
    listed = client.get("/finance/bank-accounts", headers=ana).json()
    assert {"gcash", "maya", "bdo"} <= {p["key"] for p in listed["providers"]}
    assert client.post("/finance/bank-accounts", json={"provider": "bdo", "name": "X", "accountId": "nope"}, headers=ana).status_code == 422
    bdo = a_bank(client, ana)
    assert bdo["provider"]["initials"] == "BU" and bdo["kind"] == "bank"
    gcash = a_bank(client, ana, "gcash", "GCash 0917")
    assert gcash["kind"] == "ewallet"
    ready(client, ana)
    inv = issued(client, ana)
    r = client.post(f"/finance/invoices/{inv['id']}/payments", json={"paidOn": inv["date"], "amountCentavos": 100000, "method": "check", "bankAccountId": bdo["id"]}, headers=ana)
    assert r.status_code == 422  # a check needs its number
    r = client.post(f"/finance/invoices/{inv['id']}/payments", json={"paidOn": inv["date"], "amountCentavos": 100000, "method": "check", "bankAccountId": bdo["id"],
                                                                     "checkNumber": "000123", "checkBank": "BPI"}, headers=ana)
    assert r.status_code == 201, r.text
    assert r.json()["payments"][0]["checkNumber"] == "000123" and r.json()["payments"][0]["bankAccountId"] == bdo["id"]


def test_vat_rounded_once_per_invoice(client, ana):  # noqa: F811
    ready(client, ana)
    lines = [{"description": f"Item {i}", "quantity": 1, "unitPriceCentavos": 1013} for i in range(3)]
    per_line = draft(client, ana, lines=lines, pricesIncludeTax=False)["computed"]
    client.put("/tax/profile", json={**REGISTRATION, "rounding": "invoice"}, headers=ana)
    per_invoice = draft(client, ana, lines=lines, pricesIncludeTax=False)["computed"]
    tax = lambda c: next(s["amountCentavos"] for s in c["summary"] if s["key"] == "tax")  # noqa: E731
    assert tax(per_line) == 3 * 122  # 121.56 rounds to 122 on each line
    assert tax(per_invoice) == 365  # 3,039 x 12% = 364.68, once
    assert sum(line["taxCentavos"] for line in per_invoice["lines"]) == tax(per_invoice)


def test_a_usd_bill_is_paid_at_the_days_rate_with_the_difference_to_exchange(app, client, ana):  # noqa: F811
    gain, loss = account(client, ana, "4900", "Exchange gains", "income"), account(client, ana, "6950", "Exchange losses", "expense")
    client.put("/finance/ledger/posting", json={"accounts": {"fx_gain_account_id": gain, "fx_loss_account_id": loss}}, headers=ana)
    yesterday = (date.fromisoformat(TODAY) - timedelta(days=1)).isoformat()
    assert client.put("/finance/exchange-rates", json={"currency": "USD", "on": yesterday, "rate": 56.0}, headers=ana).status_code == 200
    assert client.put("/finance/exchange-rates", json={"currency": "USD", "on": TODAY, "rate": 55.5}, headers=ana).status_code == 200
    supplier = client.post("/finance/suppliers", json={"name": "Shanghai Medical Co.", "vatRegistered": False}, headers=ana)
    assert supplier.status_code == 201, supplier.text
    expense = next(a["id"] for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"] if a["code"] == "6900")
    bill = client.post("/finance/bills", json={"supplierId": supplier.json()["id"], "billNumber": "INV-88", "billDate": yesterday, "currency": "USD",
                                                "amountsIncludeVat": True, "lines": [{"accountId": expense, "description": "Gloves, 1,000 boxes", "amountCentavos": 100000, "vat": "none"}]},
                       headers=ana)
    assert bill.status_code == 201, bill.text
    b = bill.json()
    assert b["currency"] == "USD" and b["rate"] == 56.0 and b["payableCentavos"] == 5600000 and b["foreignPayableCentavos"] == 100000
    from app.routers.payables import clear
    from app.models import Bill, User

    with app.state.sessions() as db:
        clear(db, db.scalar(select(User)), db.get(Bill, b["id"]))
        db.commit()
    paid_from = cash_in_bank(client, ana)
    v = client.post("/finance/vouchers", json={"supplierId": supplier.json()["id"], "method": "bank", "paidFromId": paid_from,
                                               "lines": [{"billId": b["id"], "amountCentavos": 5600000}]}, headers=ana)
    assert v.status_code == 201, v.text
    from app.models import PaymentVoucher

    with app.state.sessions() as db:
        db.get(PaymentVoucher, v.json()["id"]).status = "to_release"
        db.commit()
    r = client.post(f"/finance/vouchers/{v.json()['id']}/release", json={"paidOn": TODAY, "bankReference": "TT-1"}, headers=ana)
    assert r.status_code == 200, r.text
    with app.state.sessions() as db:
        voucher = db.get(PaymentVoucher, v.json()["id"])
        assert voucher.rate_e4 == 555000 and voucher.exchange_centavos == 50000  # $1,000 for 55,500 pesos, booked at 56,000: a 500-peso gain
        lines = db.scalars(select(JournalLine).where(JournalLine.entry_id == voucher.entry_id)).all()
        assert sum(x.debit_centavos for x in lines) == sum(x.credit_centavos for x in lines)
        assert any(x.account_id == gain and x.credit_centavos == 50000 for x in lines)


def test_owners_equity_closing_the_year_and_the_lock(app, client, ana):  # noqa: F811
    capital = next(a["id"] for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"] if a["code"] == "3000")
    drawings, retained = account(client, ana, "3100", "Owner's drawings", "equity"), account(client, ana, "3200", "Retained earnings", "equity")
    client.put("/finance/ledger/posting", json={"accounts": {"capital_account_id": capital, "drawings_account_id": drawings, "retained_earnings_account_id": retained}}, headers=ana)
    bdo = a_bank(client, ana)
    year_end = client.get("/finance/closing", headers=ana).json()["years"][0]["yearEnd"]
    in_year = (date.fromisoformat(year_end) - timedelta(days=10)).isoformat()
    assert client.post("/finance/equity/entries", json={"kind": "capital", "amountCentavos": 1000000, "on": in_year, "bankAccountId": bdo["id"], "owner": "Naresh Bishnoi"}, headers=ana).status_code == 201
    assert client.post("/finance/equity/entries", json={"kind": "drawing", "amountCentavos": 200000, "on": in_year, "bankAccountId": bdo["id"], "owner": "Naresh Bishnoi"}, headers=ana).status_code == 201
    statement = client.get(f"/finance/equity/statement?yearEnd={year_end}", headers=ana).json()
    rows = {r["label"]: r["amountCentavos"] for r in statement["rows"]}
    assert rows["Capital put in"] == 1000000 and rows["Drawings taken out"] == -200000 and rows["Equity at the end of the year"] == 800000

    closed = client.post("/finance/closing", json={"yearEnd": year_end, "lock": True}, headers=ana)
    assert closed.status_code == 200, closed.text
    assert closed.json()["lockedUntil"] == year_end
    assert client.post("/finance/closing", json={"yearEnd": year_end}, headers=ana).status_code == 409
    # Locked: nothing more is posted in that year.
    late = client.post("/finance/equity/entries", json={"kind": "capital", "amountCentavos": 100, "on": in_year, "bankAccountId": bdo["id"], "owner": "Naresh"}, headers=ana)
    assert late.status_code == 409 and "closed up to" in late.json()["detail"]
    after = {r["label"]: r["amountCentavos"] for r in client.get(f"/finance/equity/statement?yearEnd={year_end}", headers=ana).json()["rows"]}
    assert after["Equity at the end of the year"] == 800000  # closing moves income into equity; equity stays what it was
    assert client.put("/finance/period-lock", json={"lockedUntil": None}, headers=ana).json() == {"lockedUntil": None}
