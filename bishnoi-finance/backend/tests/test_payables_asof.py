"""Payables as of a past day are rebuilt from dated bills, payments and voids, and agree with the
ledger's payables account on that day; today's figure is unchanged (2026-10-29, as for receivables).
Needed to compare Finance's AP with Oojeema's Dec 31 / Jan 31 / Feb 28 / Mar 31 reports."""

from datetime import date, timedelta

from sqlalchemy import func, select

from app import management
from app.ledger import settings as posting_settings
from app.models import JournalEntry, JournalLine

from .test_payables import bill, supplier
from .test_concurrent_saves import app  # noqa: F401 (the SQLite / PostgreSQL fixture)
from .test_tax_api import ana, client  # noqa: F401 (fixtures)
from .test_vouchers import prepare, step, team  # noqa: F401 (fixtures)

TODAY = date.today()


def ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()


def ledger_ap(app, on: str) -> int:
    """Credit less debit on the default payables account, from approved entries dated up to the day."""
    with app.state.sessions() as db:
        account = posting_settings(db).payables_account_id
        credit, debit = db.execute(
            select(func.coalesce(func.sum(JournalLine.credit_centavos), 0), func.coalesce(func.sum(JournalLine.debit_centavos), 0))
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(JournalLine.account_id == account, JournalEntry.status == "approved", JournalEntry.entry_date <= date.fromisoformat(on))
        ).one()
    return int(credit) - int(debit)


def every_view_agrees(client, app, who, on: str) -> int:  # noqa: F811
    """The aging screen, the report, the key figures and the ledger all say the same."""
    screen = client.get("/finance/payables/aging", params={"asOf": on}, headers=who).json()["totals"]["owedCentavos"]
    report = sum(r["total"] for r in client.get("/finance/reports/payables-ageing", params={"from": on, "to": on}, headers=who).json()["rows"])
    with app.state.sessions() as db:
        key_figures = management.payables(db, date.fromisoformat(on))
    assert screen == report == key_figures == ledger_ap(app, on), (on, screen, report, key_figures, ledger_ap(app, on))
    return screen


def posted_bill(client, team, days_ago: int, number: str) -> tuple[dict, dict]:
    aubrey = team["aubrey"]
    s = supplier(client, aubrey, name=f"Synthetic supplier {number}", tin=f"12345{number[-4:]}")
    b = bill(client, aubrey, s["id"], number=number, billDate=ago(days_ago))
    for who, action in ((aubrey, "submit"), (team["malou"], "approve"), (team["rommel"], "check")):
        r = client.post(f"/finance/bills/{b['id']}/{action}", headers=who)
        assert r.status_code == 200, r.text
    return s, r.json()


def test_a_bill_paid_later_is_still_owed_on_the_earlier_day(client, app, ana, team):  # noqa: F811
    s, b = posted_bill(client, team, 60, "SI-9001")
    payable = b["payableCentavos"]
    v = prepare(client, team["cristal"], s, [{"billId": b["id"], "amountCentavos": 500_000}])
    step(client, team["cristal"], v, "submit")
    step(client, team["cristal"], v, "release", {"paidOn": ago(30), "bankReference": "SYN-1"})
    assert every_view_agrees(client, app, ana, ago(61)) == 0  # before the bill
    assert every_view_agrees(client, app, ana, ago(45)) == payable  # before the payment: owed in full
    assert every_view_agrees(client, app, ana, ago(30)) == payable - 500_000  # part paid that day
    assert every_view_agrees(client, app, ana, TODAY.isoformat()) == payable - 500_000


def test_a_payment_voided_today_still_counted_on_the_earlier_day(client, app, ana, team):  # noqa: F811
    s, b = posted_bill(client, team, 60, "SI-9002")
    payable = b["payableCentavos"]
    v = prepare(client, team["cristal"], s, [{"billId": b["id"], "amountCentavos": payable}])
    step(client, team["cristal"], v, "submit")
    step(client, team["cristal"], v, "release", {"paidOn": ago(30), "bankReference": "SYN-2"})
    step(client, team["malou"], v, "void", {"reason": "Synthetic test void"})
    assert every_view_agrees(client, app, ana, ago(30)) == 0  # paid then; the void is dated today
    assert every_view_agrees(client, app, ana, TODAY.isoformat()) == payable  # owed again from today


def test_a_bill_voided_today_was_owed_before(client, app, ana, team):  # noqa: F811
    _, b = posted_bill(client, team, 60, "SI-9003")
    r = client.post(f"/finance/bills/{b['id']}/void", json={"reason": "Synthetic test void"}, headers=team["malou"])
    assert r.status_code == 200, r.text
    assert every_view_agrees(client, app, ana, ago(45)) == b["payableCentavos"]
    assert every_view_agrees(client, app, ana, TODAY.isoformat()) == 0


def test_a_future_day_is_refused(client, ana):  # noqa: F811
    r = client.get("/finance/payables/aging", params={"asOf": (TODAY + timedelta(days=1)).isoformat()}, headers=ana)
    assert r.status_code == 422
