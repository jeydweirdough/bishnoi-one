"""Finance's desk: approvals, guarantee-letter checks and letter payments,
across every sales division Finance's grants reach."""

from tests.conftest import PDF, customer_id, field_messages, post_quote, product_ids


def letter_quote(client, as_) -> dict:
    """Ana's B2C quote for Maria Lopez, paid with a ₱960 DSWD letter."""
    ana = as_("ana")
    quote = {
        "priceType": "patient",
        "payer": "dswd",
        "lines": [{"productId": product_ids(client, ana, "b2c")["ASC-500"], "quantity": 2}],
        "letter": {"number": "DSWD-7", "issuedOn": "2026-09-10", "amountCentavos": 96000},
    }
    r = post_quote(client, ana, "b2c", customer_id(client, ana, "b2c", "Maria Lopez"), quote, letter=PDF)
    assert r.status_code == 201, r.text
    return r.json()


def discount_quote(client, as_) -> dict:
    """Grace's HOS quote with a 20% discount: over the 10% limit."""
    grace = as_("grace")
    line = {"productId": product_ids(client, grace, "hos")["PARA-SYR"], "quantity": 10, "discount": {"kind": "percent", "value": 2000}}
    r = post_quote(client, grace, "hos", customer_id(client, grace, "hos", "Riverside Medical Center"), {"priceType": "drugstore-hospital", "lines": [line]})
    assert r.status_code == 201, r.text
    return r.json()


def test_finance_sees_waiting_quotes_from_every_division(client, as_):
    letter = letter_quote(client, as_)
    discount = discount_quote(client, as_)
    joy = as_("joy")
    assert client.get("/finance/summary", headers=joy).json()["counts"] == {"approvals": 1, "letters": 1, "payments": 0}

    approvals = client.get("/finance/quotes", params={"task": "approvals"}, headers=joy).json()["items"]
    assert [q["id"] for q in approvals] == [discount["id"]]
    assert (approvals[0]["divisionName"], approvals[0]["customerName"]) == ("HOS", "Riverside Medical Center")
    assert approvals[0]["can"]["approve"] is True

    letters = client.get("/finance/quotes", params={"task": "letters"}, headers=joy).json()["items"]
    assert [q["id"] for q in letters] == [letter["id"]]


def test_only_finance_gets_the_desk(client, as_):
    assert client.get("/finance/summary", headers=as_("ana")).status_code == 403
    assert client.get("/finance/summary", headers=as_("carmen")).status_code == 403
    q = discount_quote(client, as_)
    ramon = as_("ramon")  # executives see everything, read-only
    items = client.get("/finance/quotes", params={"task": "approvals"}, headers=ramon).json()["items"]
    assert items[0]["can"]["approve"] is False
    assert client.post(f"/finance/quotes/{q['id']}/approval", json={"decision": "approve"}, headers=ramon).status_code == 403


def test_approving_a_big_discount(client, as_):
    q = discount_quote(client, as_)
    joy = as_("joy")
    assert client.post(f"/finance/quotes/{q['id']}/approval", json={"decision": "reject"}, headers=joy).status_code == 422
    r = client.post(f"/finance/quotes/{q['id']}/approval", json={"decision": "approve", "note": "Matches the Q4 deal."}, headers=joy)
    assert r.status_code == 200
    assert (r.json()["state"], r.json()["approval"]["by"]["name"]) == ("ready", "Joy Navarro")
    assert client.post(f"/finance/quotes/{q['id']}/approval", json={"decision": "approve"}, headers=joy).status_code == 409

    seen_by_rep = client.get(f"/sales/quotes/{q['id']}", headers=as_("grace")).json()
    assert (seen_by_rep["approval"]["status"], seen_by_rep["approval"]["note"]) == ("approved", "Matches the Q4 deal.")
    done = client.get("/finance/quotes", params={"task": "approvals", "state": "done"}, headers=joy).json()["items"]
    assert [x["id"] for x in done] == [q["id"]]


def test_a_rejected_approval_shows_why(client, as_):
    q = discount_quote(client, as_)
    r = client.post(f"/finance/quotes/{q['id']}/approval", json={"decision": "reject", "note": "Too deep; 10% at most."}, headers=as_("joy"))
    assert (r.json()["state"], r.json()["approval"]["note"]) == ("rejected", "Too deep; 10% at most.")


def test_checking_a_letter_then_recording_payments(client, as_):
    q = letter_quote(client, as_)
    joy = as_("joy")
    pay = lambda amount: client.post(  # noqa: E731
        f"/finance/quotes/{q['id']}/payments", json={"paidOn": "2026-09-15", "amountCentavos": amount, "reference": "OR-1"}, headers=joy
    )
    assert pay(10000).status_code == 409  # not checked yet

    letter = client.get(f"/finance/quotes/{q['id']}/letter", headers=joy)
    assert letter.status_code == 200 and letter.content == PDF
    r = client.post(f"/finance/quotes/{q['id']}/letter-check", json={"decision": "approve"}, headers=joy)
    assert (r.json()["letter"]["status"], r.json()["state"]) == ("verified", "ready")
    assert client.get("/finance/summary", headers=joy).json()["counts"]["payments"] == 1

    assert pay(50000).json()["payment"]["status"] == "partial"
    r = pay(50000)
    assert r.status_code == 422 and field_messages(r) == {"amountCentavos": "Only ₱460.00 is left on this letter."}
    paid = pay(46000).json()
    assert (paid["payment"]["status"], paid["payment"]["paidCentavos"], len(paid["payment"]["payments"])) == ("paid", 96000, 2)
    done = client.get("/finance/quotes", params={"task": "payments", "state": "done"}, headers=joy).json()["items"]
    assert [x["id"] for x in done] == [q["id"]]
