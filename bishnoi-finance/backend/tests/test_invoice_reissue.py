"""Cancel and reissue (Rommel Q20: a posted invoice is never edited; decided 2026-10-22:
Plans/Plan - Replaces invoice): the invoice is voided as Void does, a draft copying it is
made and marked as its replacement, dated today; both say so (never on the printout)."""

from datetime import date, timedelta

from .test_invoices import draft, ready
from .test_ledger import balances
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)

TODAY = date.today().isoformat()


def issue(client, who, inv) -> dict:
    r = client.post(f"/finance/invoices/{inv['id']}/issue", json={}, headers=who)
    assert r.status_code == 200, r.text
    return r.json()


def test_cancel_and_reissue_copies_it_and_links_both(client, ana):
    ready(client, ana)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    first = issue(client, ana, draft(client, ana, invoiceDate=yesterday, customerTin="123-456-789-000", reference="PO-77"))
    r = client.post(f"/finance/invoices/{first['id']}/reissue", json={"reason": "Wrong TIN"}, headers=ana)
    assert r.status_code == 201, r.text
    new = r.json()
    # A draft copying it, dated today (changeable before issuing), marked as its replacement.
    assert (new["status"], new["number"], new["date"]) == ("draft", None, TODAY)
    assert (new["customer"]["name"], new["customer"]["tin"], new["reference"], new["lines"]) == (first["customer"]["name"], "123-456-789-000", "PO-77", first["lines"])
    assert new["replaces"]["number"] == first["number"] and new["replaces"]["reason"] == "Wrong TIN"
    # The old one is voided exactly as Void does, and knows what replaces it.
    old = client.get(f"/finance/invoices/{first['id']}", headers=ana).json()
    assert (old["status"], old["voidReason"]) == ("void", "Wrong TIN") and old["replacedBy"] == {"id": new["id"], "number": None, "status": "draft"}
    assert balances(client, ana) == {"1100": 0, "4000": 0, "2200": 0}
    # Corrected and issued: the next number, and the journal says what it replaces.
    fixed = issue(client, ana, new)
    assert fixed["number"] == "SI-000102" and fixed["replaces"]["number"] == "SI-000101"
    memos = [e["memo"] for e in client.get("/finance/ledger/entries", headers=ana).json()["items"]]
    assert any(m.startswith("SI-000102: sale to") and m.endswith("replacing SI-000101") for m in memos)
    # Lists carry it too.
    listed = {i["number"]: i for i in client.get("/finance/invoices", headers=ana).json()["items"]}
    assert listed["SI-000101"]["replacedBy"]["number"] == "SI-000102" and listed["SI-000102"]["replaces"]["number"] == "SI-000101"


def test_only_one_replacement_and_a_deleted_draft_frees_it(client, ana):
    ready(client, ana)
    first = issue(client, ana, draft(client, ana))
    new = client.post(f"/finance/invoices/{first['id']}/reissue", json={"reason": "Wrong address"}, headers=ana).json()
    again = client.post(f"/finance/invoices/{first['id']}/reissue", json={}, headers=ana)
    assert again.status_code == 409 and "already being replaced" in again.json()["detail"]
    assert client.delete(f"/finance/invoices/{new['id']}", headers=ana).status_code == 204
    # The cancelled one can be replaced again, without cancelling it twice.
    redo = client.post(f"/finance/invoices/{first['id']}/reissue", json={}, headers=ana)
    assert redo.status_code == 201 and redo.json()["replaces"]["number"] == first["number"]


def test_what_stops_a_reissue(client, ana, ben):
    ready(client, ana)
    first = issue(client, ana, draft(client, ana))
    # A reason is needed to cancel; staff make drafts but don't void.
    assert client.post(f"/finance/invoices/{first['id']}/reissue", json={}, headers=ana).status_code == 422
    assert client.post(f"/finance/invoices/{first['id']}/reissue", json={"reason": "Wrong TIN"}, headers=ben).status_code == 403
    # Payments recorded: take them off first, as with Void.
    client.post(f"/finance/invoices/{first['id']}/payments", json={"paidOn": TODAY, "amountCentavos": 1000, "method": "cash"}, headers=ana)
    paid = client.post(f"/finance/invoices/{first['id']}/reissue", json={"reason": "Wrong TIN"}, headers=ana)
    assert paid.status_code == 409 and "take them off first" in paid.json()["detail"]
    # A draft is changed directly.
    d = draft(client, ana)
    assert client.post(f"/finance/invoices/{d['id']}/reissue", json={"reason": "x y z"}, headers=ana).status_code == 409


def test_plain_void_still_works_and_leaves_no_replacement(client, ana):
    ready(client, ana)
    first = issue(client, ana, draft(client, ana))
    voided = client.post(f"/finance/invoices/{first['id']}/void", json={"reason": "Customer cancelled"}, headers=ana).json()
    assert voided["status"] == "void" and voided["replacedBy"] is None and voided["replaces"] is None
