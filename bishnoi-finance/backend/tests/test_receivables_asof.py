"""Receivables as of a past day are rebuilt from dated payments, take-offs and
voids, and agree with the ledger's receivables account on that day; today's
figure is unchanged."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from app import management

from .test_invoices import issued, ready
from .test_tax_api import ana, app, client  # noqa: F401 (fixtures)

TODAY = date.today()


def ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()


def owed(client, who, on: str) -> int:
    return client.get("/finance/receivables", params={"on": on}, headers=who).json()["totalCentavos"]


def ledger_ar(client, who, on: str) -> int:
    rows = client.get("/finance/ledger/trial-balance", params={"to": on}, headers=who).json()["rows"]
    return next((r["balanceCentavos"] for r in rows if r["account"]["code"] == "1100"), 0)


def report_owed(client, who, on: str) -> int:
    body = client.get("/finance/reports/receivables-ageing", params={"from": on, "to": on}, headers=who).json()
    return sum(r["total"] for r in body["rows"])


def every_view_agrees(client, app, who, on: str) -> int:  # noqa: F811
    """The receivables screen, the report, the key figures and the ledger all say the same."""
    screen = owed(client, who, on)
    with app.state.sessions() as db:
        key_figures = management.receivables(db, date.fromisoformat(on), ZoneInfo("Asia/Manila"))
    assert screen == report_owed(client, who, on) == key_figures == ledger_ar(client, who, on), on
    return screen


def pay(client, who, inv, on: str, amount: int, cwt: int = 0):
    body = {"paidOn": on, "amountCentavos": amount, "method": "cash", **({"cwtCentavos": cwt, "cwtAtc": "WC158"} if cwt else {})}
    r = client.post(f"/finance/invoices/{inv['id']}/payments", json=body, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def test_an_invoice_paid_later_is_still_owed_on_the_earlier_day(client, app, ana):  # noqa: F811
    ready(client, ana)
    inv = issued(client, ana, invoiceDate=ago(60))  # 2,240.00, like the January invoice paid in February
    pay(client, ana, inv, ago(30), 224000)
    assert every_view_agrees(client, app, ana, ago(61)) == 0  # before the invoice
    assert every_view_agrees(client, app, ana, ago(45)) == 224000  # before the payment: owed in full
    assert every_view_agrees(client, app, ana, ago(30)) == 0  # paid that day
    assert every_view_agrees(client, app, ana, TODAY.isoformat()) == 0


def test_part_payments_and_withholding_count_from_their_own_dates(client, app, ana):  # noqa: F811
    ready(client, ana)
    inv = issued(client, ana, invoiceDate=ago(60))
    pay(client, ana, inv, ago(40), 100000)
    pay(client, ana, inv, ago(20), 120000, cwt=4000)  # the rest, 40.00 of it withheld by the customer
    assert every_view_agrees(client, app, ana, ago(50)) == 224000
    assert every_view_agrees(client, app, ana, ago(30)) == 124000
    assert every_view_agrees(client, app, ana, ago(20)) == 0


def test_a_payment_taken_off_today_still_counted_on_earlier_days(client, app, ana):  # noqa: F811
    ready(client, ana)
    inv = issued(client, ana, invoiceDate=ago(60))
    payment = pay(client, ana, inv, ago(30), 224000)["payments"][0]["id"]
    assert client.delete(f"/finance/invoices/{inv['id']}/payments/{payment}", headers=ana).status_code == 200
    # Its reversal is dated today, as the ledger has it: settled in between, owed again from today.
    assert every_view_agrees(client, app, ana, ago(10)) == 0
    assert every_view_agrees(client, app, ana, TODAY.isoformat()) == 224000


def test_an_invoice_voided_today_was_owed_before_today(client, app, ana):  # noqa: F811
    ready(client, ana)
    inv = issued(client, ana, invoiceDate=ago(60))
    assert client.post(f"/finance/invoices/{inv['id']}/void", json={"reason": "Wrong customer"}, headers=ana).status_code == 200
    assert every_view_agrees(client, app, ana, ago(10)) == 224000
    assert every_view_agrees(client, app, ana, TODAY.isoformat()) == 0


def test_todays_figure_is_what_it_was(client, app, ana):  # noqa: F811
    ready(client, ana)
    late = issued(client, ana, invoiceDate=ago(75), termsDays=30)
    fresh = issued(client, ana, customerName="Watsons BGC")
    pay(client, ana, fresh, TODAY.isoformat(), 24000)
    got = client.get("/finance/receivables", headers=ana).json()
    assert {b["key"]: b["amountCentavos"] for b in got["buckets"]} == {"current": 200000, "d1_30": 0, "d31_60": 224000, "d61_90": 0, "over_90": 0}
    assert got["customers"][0]["invoices"][0]["number"] == late["number"]
    assert every_view_agrees(client, app, ana, TODAY.isoformat()) == 424000
