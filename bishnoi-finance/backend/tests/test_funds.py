"""Marketing requests: approved in the CRM, released here, liquidated receipt by
receipt, and settled as unused funds returned or an amount reimbursed."""

import base64
from datetime import UTC, date, datetime

from .test_tax_api import CRM_KEY, app, ana, ben, client  # noqa: F401 (fixtures)

KEY = {"X-Nabhi-Key": CRM_KEY}
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 100).decode()


def approved(client, source_id="req-1", liquidate=True, amount=500000):
    body = {
        "sourceId": source_id, "number": f"FR-202609-{source_id[-4:]}", "requesterName": "Rico Santos", "requesterEmail": "rico@example.com",
        "teamName": "North Luzon", "purpose": "Partnership dinner", "details": "Dinner with Dr. Reyes' clinic", "customerName": "Reyes Clinic",
        "liquidate": liquidate, "requestedCentavos": amount, "approvedCentavos": amount, "approvedByName": "Tess Aquino",
        "approvedAt": datetime.now(UTC).isoformat(),
    }
    r = client.post("/integration/funds/requests", json=body, headers=KEY)
    assert r.status_code == 201, r.text
    return r.json()


def categories(client) -> dict[str, dict]:
    return {c["name"]: c for c in client.get("/integration/funds/categories", headers=KEY).json()["items"]}


def spend(client, amount, category, source_id="req-1", receipt=True):
    body = {"spentOn": date.today().isoformat(), "description": "Dinner", "categoryId": category["id"], "amountCentavos": amount, "by": "Rico Santos"}
    if receipt:
        body["receipt"] = {"name": "receipt.png", "contentType": "image/png", "data": PNG}
    else:
        body["noReceiptReason"] = "The jeepney gives none"
    r = client.post(f"/integration/funds/requests/{source_id}/expenses", json=body, headers=KEY)
    assert r.status_code == 201, r.text
    return r.json()


def release(client, who, request_id, amount=500000):
    r = client.post(f"/finance/funds/{request_id}/release", json={"amountCentavos": amount, "method": "cash"}, headers=who)
    assert r.status_code == 200, r.text
    return r.json()


def check_all(client, who, req):
    for e in req["expenses"]:
        client.patch(f"/finance/funds/{req['id']}/expenses/{e['id']}", json={"accepted": True}, headers=who)
    r = client.post(f"/finance/funds/{req['id']}/finish-check", headers=who)
    assert r.status_code == 200, r.text
    return r.json()


def test_only_an_app_with_a_key_sends_requests(client):
    assert client.post("/integration/funds/requests", json={}).status_code == 401
    assert client.get("/integration/funds/categories", headers={"X-Nabhi-Key": "x" * 32}).status_code == 401


def test_sent_twice_is_one_request(client, ben):
    first = approved(client)
    again = approved(client)
    assert first["id"] == again["id"]
    assert [r["number"] for r in client.get("/finance/funds", headers=ben).json()["items"]] == [first["number"]]
    assert client.get("/finance/funds/counts", headers=ben).json()["to_release"] == 1


def test_not_liquidated_closes_on_release(client, ben):
    req = approved(client, liquidate=False)
    done = release(client, ben, req["id"])
    assert done["status"] == "closed" and done["release"]["methodLabel"] == "Cash"
    assert [e["kind"] for e in done["events"]] == ["approved", "released", "closed"]


def test_unused_funds_are_returned(client, ben):
    req = release(client, ben, approved(client)["id"])
    assert req["status"] == "to_liquidate" and req["release"]["liquidateBy"]
    cats = categories(client)
    spend(client, 320000, cats["Food"])
    # Spending that's the person's own doesn't lower the unused funds.
    spend(client, 50000, cats["Personal"], receipt=False)
    sent = client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico Santos"}, headers=KEY).json()
    assert sent["status"] == "to_check" and sent["tally"]["spentCentavos"] == 370000
    done = check_all(client, ben, sent)
    assert done["status"] == "to_return" and done["returnDueCentavos"] == 180000
    assert done["tally"] == {"spentCentavos": 370000, "coveredCentavos": 320000, "ownCentavos": 50000, "refusedCentavos": 0, "balanceCentavos": 180000}
    part = client.post(f"/finance/funds/{req['id']}/returned", json={"amountCentavos": 100000}, headers=ben).json()
    assert part["status"] == "to_return" and part["returnedCentavos"] == 100000
    assert client.post(f"/finance/funds/{req['id']}/returned", json={"amountCentavos": 90000}, headers=ben).status_code == 422
    done = client.post(f"/finance/funds/{req['id']}/returned", json={"amountCentavos": 80000}, headers=ben).json()
    assert done["status"] == "closed"


def test_spending_more_is_reimbursed_only_where_the_category_is(client, ben):
    req = release(client, ben, approved(client, amount=200000)["id"], amount=200000)
    cats = categories(client)
    spend(client, 250000, cats["Food"])
    spend(client, 30000, cats["Personal"])
    sent = client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico"}, headers=KEY).json()
    done = check_all(client, ben, sent)
    assert done["status"] == "to_reimburse" and done["reimburseDueCentavos"] == 50000
    closed = client.post(f"/finance/funds/{req['id']}/reimbursed", json={"amountCentavos": 50000, "method": "ewallet", "reference": "GC-1"}, headers=ben).json()
    assert closed["status"] == "closed"


def test_a_refused_receipt_does_not_count_and_can_be_sent_back(client, ben):
    req = release(client, ben, approved(client)["id"])
    meal = spend(client, 400000, categories(client)["Food"])["expenses"][0]
    client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico"}, headers=KEY)
    r = client.patch(f"/finance/funds/{req['id']}/expenses/{meal['id']}", json={"accepted": False}, headers=ben)
    assert r.status_code == 422  # needs a reason
    back = client.post(f"/finance/funds/{req['id']}/send-back", json={"note": "The receipt is blurry"}, headers=ben).json()
    assert back["status"] == "to_liquidate" and back["sentBackNote"] == "The receipt is blurry"
    # Fixed and sent again; this time refused, so all of it is unused funds.
    client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico"}, headers=KEY)
    client.patch(f"/finance/funds/{req['id']}/expenses/{meal['id']}", json={"accepted": False, "refusedReason": "Not a company expense"}, headers=ben)
    done = client.post(f"/finance/funds/{req['id']}/finish-check", headers=ben).json()
    assert done["status"] == "to_return" and done["returnDueCentavos"] == 500000


def test_every_receipt_is_decided_before_the_check_is_done(client, ben):
    req = release(client, ben, approved(client)["id"])
    spend(client, 100000, categories(client)["Transportation"])
    client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico"}, headers=KEY)
    assert client.post(f"/finance/funds/{req['id']}/finish-check", headers=ben).status_code == 409


def test_the_receipt_is_kept_and_only_changes_while_liquidating(client, ben):
    req = release(client, ben, approved(client)["id"])
    e = spend(client, 100000, categories(client)["Transportation"])["expenses"][0]
    r = client.get(f"/integration/funds/requests/req-1/expenses/{e['id']}/receipt", headers=KEY)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert client.get(f"/finance/funds/{req['id']}/expenses/{e['id']}/receipt", headers=ben).status_code == 200
    client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico"}, headers=KEY)
    assert client.delete(f"/integration/funds/requests/req-1/expenses/{e['id']}", headers=KEY).status_code == 409


def test_cancelled_before_release_only(client, ben):
    approved(client)
    done = client.post("/integration/funds/requests/req-1/cancel", json={"by": "Rico", "reason": "The dinner was moved"}, headers=KEY).json()
    assert done["status"] == "cancelled"
    other = approved(client, "req-2")
    release(client, ben, other["id"])
    assert client.post("/integration/funds/requests/req-2/cancel", json={"by": "Rico"}, headers=KEY).status_code == 409


def test_not_more_than_approved_and_categories_are_admins(client, ana, ben):
    req = approved(client, amount=100000)
    r = client.post(f"/finance/funds/{req['id']}/release", json={"amountCentavos": 100001, "method": "cash"}, headers=ben)
    assert r.status_code == 422
    assert client.post("/finance/funds/categories", json={"name": "Gifts", "reimbursable": False}, headers=ben).status_code == 403
    # A category needs the expense account its receipts post to.
    assert client.post("/finance/funds/categories", json={"name": "Gifts", "reimbursable": False}, headers=ana).status_code == 422
    other = next(a for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"] if a["code"] == "6900")
    made = client.post("/finance/funds/categories", json={"name": "Gifts", "reimbursable": False, "accountId": other["id"]}, headers=ana)
    assert made.status_code == 201 and made.json()["reimbursable"] is False
    # A sub-category follows its category, and names repeat only across categories.
    sub = client.post("/finance/funds/categories", json={"name": "Flowers", "parentId": made.json()["id"], "reimbursable": True}, headers=ana).json()
    assert sub["label"] == "Gifts › Flowers" and sub["reimbursable"] is False and sub["account"]["code"] == "6900"
    again = client.post("/finance/funds/categories", json={"name": "Flowers", "parentId": made.json()["id"]}, headers=ana)
    assert again.status_code == 422

