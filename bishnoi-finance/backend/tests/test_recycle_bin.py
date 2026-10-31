"""Data clean-up and the recycle bin in Finance (2026-10-30, app/recycle_bin.py): an issued invoice goes with its
journal entry, so the books stay balanced; restore brings both back; a closed period refuses."""

from .test_invoices import TODAY, issued, ready
from .test_tax_api import ana, app, client  # noqa: F401 (fixtures)


def entries(client, ana):  # noqa: F811
    r = client.get("/finance/ledger/entries", headers=ana)
    assert r.status_code == 200, r.text
    body = r.json()
    return body["items"] if isinstance(body, dict) else body


def test_an_issued_invoice_goes_with_its_journal_entry_and_comes_back(client, ana):  # noqa: F811
    ready(client, ana)
    inv = issued(client, ana)
    before = len(entries(client, ana))
    assert before >= 1
    first = client.post("/data-cleanup/kinds/invoices/delete", json={"ids": [inv["id"]]}, headers=ana)
    assert first.status_code == 409 and "posted" in first.text
    done = client.post("/data-cleanup/kinds/invoices/delete", json={"ids": [inv["id"]], "confirmPosted": True}, headers=ana)
    assert done.status_code == 200, done.text
    assert client.get(f"/finance/invoices/{inv['id']}", headers=ana).status_code == 404
    assert len(entries(client, ana)) == before - 1
    entry = client.get("/data-cleanup/bin", headers=ana).json()["items"][0]
    assert client.post(f"/data-cleanup/bin/{entry['id']}/restore", headers=ana).status_code == 200
    assert client.get(f"/finance/invoices/{inv['id']}", headers=ana).status_code == 200
    assert len(entries(client, ana)) == before


def test_a_closed_period_refuses(app, client, ana):  # noqa: F811
    from datetime import date

    from app.models import LedgerSettings

    ready(client, ana)
    inv = issued(client, ana)
    with app.state.sessions() as db:  # the period closed up to the invoice's day (the screen allows only past days)
        db.query(LedgerSettings).one().locked_until = date.fromisoformat(TODAY)
        db.commit()
    r = client.post("/data-cleanup/kinds/invoices/delete", json={"ids": [inv["id"]], "confirmPosted": True}, headers=ana)
    assert r.status_code == 409 and "closed period" in r.text
