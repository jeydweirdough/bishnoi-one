"""Only correctly delegated, company-bound accounting reads may return figures."""
import pytest
from datetime import date
from app import platform_pass, bir_reports, platform_links
from app.models import Account, JournalEntry, JournalLine
from .test_tax_api import ana, app, ben, client  # noqa: F401
from .test_invoices import ready, issued

URL = "/finance/assistant/monthly"
HEADERS = {"Authorization": "Bearer delegated-pass"}


@pytest.fixture
def delegated(monkeypatch, app):
    owner = {"id": "company-id", "slug": "getmeds", "name": "Getmeds", "currency": "PHP", "timezone": "Asia/Manila", "status": "active"}
    monkeypatch.setattr(platform_links, "database_company", lambda *args, **kwargs: owner)
    claims = {"kind": "assistant-read", "tool": "monthly-summary", "company": "company-id", "companySlug": "getmeds",
              "email": "reader@example.test", "permissions": ["journal.view"], "admin": False}
    monkeypatch.setattr(platform_pass, "check_for", lambda *args: claims)
    return claims


def read(client, month="2026-10"):
    return client.post(URL, headers=HEADERS, json={"month": month})


def test_signature_authority_and_binding_are_required(client, app, delegated, monkeypatch):
    assert client.post(URL, json={"month": "2026-10"}).status_code == 401
    delegated["companySlug"] = "another-company"
    assert read(client).status_code == 403
    delegated["companySlug"] = "getmeds"
    delegated["company"] = "other-id"
    assert read(client).status_code == 403
    delegated["company"] = "company-id"
    delegated["permissions"] = ["invoices.view"]
    assert read(client).status_code == 403
    delegated["permissions"] = ["journal.view"]
    original = platform_links.database_company
    monkeypatch.setattr(platform_links, "database_company", lambda *args, **kwargs: None)
    assert read(client).status_code == 503
    monkeypatch.setattr(platform_links, "database_company", original)
    def invalid(*args): raise platform_pass.PassRefused("bad")
    monkeypatch.setattr(platform_pass, "check_for", invalid)
    assert read(client).status_code == 401


def test_empty_data_is_unavailable_not_invented_zero(client, delegated):
    r = read(client)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["revenueCentavos"] is None and d["profitCentavos"] is None and d["expensesCentavos"] is None
    assert d["missing"] and d["sources"]
    assert read(client, "2026-13").status_code == 422
    assert client.post(URL, headers=HEADERS, json={"month": "2026-10", "sql": "DROP TABLE"}).status_code == 422


def test_profit_uses_only_approved_journals_and_matches_existing_statement(client, app, delegated):
    with app.state.sessions() as db:
        income = Account(code="AI-INCOME", name="Income", type="income")
        expense = Account(code="AI-EXPENSE", name="Expenses", type="expense")
        db.add_all([income, expense]); db.flush()
        for i, (status, earned, spent) in enumerate([("approved", 500000, 200000), ("waiting", 900000, 0), ("rejected", 800000, 0)]):
            entry = JournalEntry(number=f"AI-{i}", entry_date=date(2026, 10, 1), memo="Test", posted_by="Test", status=status)
            db.add(entry); db.flush()
            db.add(JournalLine(entry_id=entry.id, account_id=income.id, debit_centavos=0, credit_centavos=earned))
            if spent:
                db.add(JournalLine(entry_id=entry.id, account_id=expense.id, debit_centavos=spent, credit_centavos=0))
        db.commit()
        standard = bir_reports.income_statement(db, date(2026, 10, 1), date(2026, 10, 31))["totals"]
    r = read(client)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["profitCentavos"] == standard["netCentavos"] == 300000
    assert d["expensesCentavos"] == 200000 and d["incomeCentavos"] == 500000
    assert d["approvedJournalLines"] == 2


def test_revenue_uses_issued_invoices_excluding_vat(client, ana, delegated):
    ready(client, ana)
    issued(client, ana)
    month = date.today().strftime("%Y-%m")
    r = read(client, month)
    assert r.status_code == 200, r.text
    assert r.json()["revenueCentavos"] == 200000  # issued total 224000, VAT 24000


def test_delegated_read_pass_cannot_open_a_session_or_write(client, delegated):
    r = client.post("/auth/platform", json={"pass": "delegated-read-pass-long-enough"})
    assert r.status_code == 401, r.text
    assert client.post("/finance/ledger/entries", headers=HEADERS, json={}).status_code == 401
