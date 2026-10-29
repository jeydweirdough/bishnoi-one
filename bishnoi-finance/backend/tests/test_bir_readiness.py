"""BIR readiness (2026-10-29): each tax list against the books for the same period. Clean records
agree everywhere; an entry the tax lists don't read shows as a gap with the entry named, the way
Oojeema's lists silently leave out journal entries to VAT and withholding accounts."""

from datetime import date, timedelta

from app.ledger import Leg, post
from app.ledger import settings as posting_settings
from app.models import Account

from .test_invoices import issued, ready
from .test_payables_asof import ago, posted_bill
from .test_concurrent_saves import app  # noqa: F401 (the SQLite / PostgreSQL fixture)
from .test_tax_api import ana, client  # noqa: F401 (fixtures)
from .test_vouchers import prepare, step, team  # noqa: F401 (fixtures)

TODAY = date.today()


def readiness(client, who, start: str, end: str) -> dict:
    r = client.get("/finance/bir/readiness", params={"start": start, "end": end}, headers=who)
    assert r.status_code == 200, r.text
    return {c["key"]: c for c in r.json()["checks"]}


def records(client, ana, team):  # noqa: F811
    """A supplier bill with VAT and tax withheld, part paid; a sale with VAT, paid with tax withheld."""
    s, b = posted_bill(client, team, 40, "SI-7001")
    v = prepare(client, team["cristal"], s, [{"billId": b["id"], "amountCentavos": 300_000}])
    step(client, team["cristal"], v, "submit")
    step(client, team["cristal"], v, "release", {"paidOn": ago(20), "bankReference": "SYN-R1"})
    ready(client, ana)
    inv = issued(client, ana, invoiceDate=ago(30))
    body = {"paidOn": ago(10), "amountCentavos": inv["totalCentavos"] - 2000, "method": "cash", "cwtCentavos": 2000, "cwtAtc": "WC158"}
    r = client.post(f"/finance/invoices/{inv['id']}/payments", json=body, headers=ana)
    assert r.status_code == 201, r.text
    return b


def test_clean_records_agree_with_the_books_everywhere(client, ana, team):  # noqa: F811
    records(client, ana, team)
    checks = readiness(client, ana, ago(60), TODAY.isoformat())
    for key in ("output_vat", "input_vat", "ewt", "cwt", "receivables", "payables"):
        assert checks[key]["status"] == "agrees", (key, checks[key])
        assert checks[key]["otherSources"] == []
    assert checks["input_vat"]["listCentavos"] > 0 and checks["ewt"]["listCentavos"] > 0 and checks["cwt"]["listCentavos"] == 2000


def test_a_journal_entry_to_input_vat_shows_as_a_gap_with_the_entry_named(client, app, ana, team):  # noqa: F811
    records(client, ana, team)
    with app.state.sessions() as db:
        s = posting_settings(db)
        vat, cash = db.get(Account, s.input_tax_account_id), db.get(Account, s.cash_account_id)
        post(db, date.fromisoformat(ago(5)), "Synthetic import VAT paid to customs", [Leg(vat, debit=12_000), Leg(cash, credit=12_000)], "Synthetic", source="manual")
        db.commit()
    c = readiness(client, ana, ago(60), TODAY.isoformat())["input_vat"]
    assert c["status"] == "differs" and c["differenceCentavos"] == -12_000
    [other] = c["otherSources"]
    assert other["source"] == "manual" and other["centavos"] == 12_000 and other["listed"][0]["memo"].startswith("Synthetic import VAT")


def test_a_bill_voided_in_a_later_period_shows_as_a_difference(client, ana, team):  # noqa: F811
    _, b = posted_bill(client, team, 40, "SI-7002")
    r = client.post(f"/finance/bills/{b['id']}/void", json={"reason": "Synthetic test void"}, headers=team["malou"])
    assert r.status_code == 200, r.text
    # The bill's own period (it's dated 40 days ago; the void is today): the list leaves it out, the books keep it.
    first = readiness(client, ana, ago(60), ago(1))["input_vat"]
    assert first["status"] == "differs" and first["listCentavos"] == 0 and first["booksCentavos"] == b["vatCentavos"]
    assert any("voided in a later period" in cause for cause in first["causes"])
    # Both periods together net to nothing on both sides.
    assert readiness(client, ana, ago(60), TODAY.isoformat())["input_vat"]["status"] == "agrees"


def test_an_end_before_the_start_is_refused(client, ana):  # noqa: F811
    r = client.get("/finance/bir/readiness", params={"start": TODAY.isoformat(), "end": (TODAY - timedelta(days=1)).isoformat()}, headers=ana)
    assert r.status_code == 422
