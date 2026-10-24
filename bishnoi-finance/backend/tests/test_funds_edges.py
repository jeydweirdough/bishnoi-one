"""Fund requests, the less-trodden paths: nothing spent, spent to the
centavo, less released than approved, Finance re-sorting a receipt, a step
refused with its entry, lateness, receipts refused at the door, steps out of
turn, and two apps whose requests never meet."""

import base64
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import ExpenseCategory, FundRequest
from app.routers.auth import attempts

from .test_funds import KEY, PNG, approved, categories, release, spend
from .test_ledger import balances
from .test_tax_api import CRM_KEY, app, ana, ben, client  # noqa: F401 (fixtures)

PHARMACY_KEY = "pharmacy-key-that-is-long-enough-5678"


def manila_today() -> date:
    return datetime.now(ZoneInfo("Asia/Manila")).date()


def submit(client, source_id="req-1"):
    r = client.post(f"/integration/funds/requests/{source_id}/submit", json={"by": "Rico Santos"}, headers=KEY)
    assert r.status_code == 200, r.text
    return r.json()


def accept_all(client, who, req):
    for e in req["expenses"]:
        client.patch(f"/finance/funds/{req['id']}/expenses/{e['id']}", json={"accepted": True}, headers=who)


def finish(client, who, request_id):
    r = client.post(f"/finance/funds/{request_id}/finish-check", headers=who)
    assert r.status_code == 200, r.text
    return r.json()


def test_nothing_spent_comes_back_in_full(client, ana, ben):
    req = release(client, ben, approved(client)["id"])  # 5,000 in cash
    sent = submit(client)
    assert sent["status"] == "to_check" and sent["expenses"] == []
    done = finish(client, ana, req["id"])
    assert done["status"] == "to_return" and done["returnDueCentavos"] == 500000
    # No receipts, so nothing is expensed: the release is the only entry so far.
    assert len(done["entries"]) == 1
    closed = client.post(f"/finance/funds/{req['id']}/returned", json={"amountCentavos": 500000}, headers=ben).json()
    assert closed["status"] == "closed"
    assert balances(client, ben) == {"1000": 0, "1200": 0}


def test_spent_to_the_centavo_closes_at_the_check(client, ana, ben):
    req = release(client, ben, approved(client)["id"])
    spend(client, 500000, categories(client)["Transportation"])
    accept_all(client, ana, submit(client))
    done = finish(client, ana, req["id"])
    assert done["status"] == "closed" and done["returnDueCentavos"] == 0 and done["reimburseDueCentavos"] == 0
    assert balances(client, ben) == {"1000": -500000, "1200": 0, "6200": 500000}


def test_only_what_was_released_counts(client, ana, ben):
    req = release(client, ben, approved(client)["id"], amount=300000)  # 3,000 of the 5,000 approved
    assert req["release"]["amountCentavos"] == 300000 and req["approvedCentavos"] == 500000
    spend(client, 350000, categories(client)["Transportation"])
    accept_all(client, ana, submit(client))
    done = finish(client, ana, req["id"])
    assert done["status"] == "to_reimburse" and done["reimburseDueCentavos"] == 50000


def test_finance_can_re_sort_a_receipt_while_reviewing(client, ana, ben):
    req = release(client, ben, approved(client)["id"])
    cats = categories(client)
    # Filed as the person's own; Finance sees it was a taxi to the client.
    taxi = spend(client, 100000, cats["Personal"])["expenses"][0]
    assert taxi["covered"] is False
    submit(client)
    bad = client.patch(f"/finance/funds/{req['id']}/expenses/{taxi['id']}", json={"categoryId": "no-such-category"}, headers=ana)
    assert bad.status_code == 422
    moved = client.patch(
        f"/finance/funds/{req['id']}/expenses/{taxi['id']}", json={"categoryId": cats["Transportation"]["id"], "accepted": True}, headers=ana
    ).json()
    assert moved["expenses"][0]["category"]["name"] == "Transportation" and moved["expenses"][0]["covered"] is True
    done = finish(client, ana, req["id"])
    assert done["tally"]["coveredCentavos"] == 100000 and done["returnDueCentavos"] == 400000


def test_a_step_and_its_entry_stand_or_fall_together(client, ana, ben):
    req = approved(client)
    # Nobody has said which account cash is paid out of.
    client.put("/finance/ledger/posting", json={"accounts": {"cash_account_id": None}}, headers=ana)
    refused = client.post(f"/finance/funds/{req['id']}/release", json={"amountCentavos": 500000, "method": "cash"}, headers=ben)
    assert refused.status_code == 409
    still = client.get(f"/finance/funds/{req['id']}", headers=ben).json()
    assert still["status"] == "to_release" and still["release"] is None and still["entries"] == []
    assert [e["kind"] for e in still["events"]] == ["approved"]
    assert client.get("/finance/ledger/entries", headers=ben).json()["items"] == []
    # Paid by bank transfer instead, it goes through.
    paid = client.post(f"/finance/funds/{req['id']}/release", json={"amountCentavos": 500000, "method": "bank"}, headers=ben)
    assert paid.status_code == 200 and paid.json()["release"]["methodLabel"] == "Bank transfer"


def test_a_category_without_an_account_holds_the_review(app, client, ana, ben):
    req = release(client, ben, approved(client)["id"])
    transport = categories(client)["Transportation"]
    spend(client, 100000, transport)
    accept_all(client, ana, submit(client))
    with app.state.sessions() as db:
        db.get(ExpenseCategory, transport["id"]).account_id = None
        db.commit()
    assert client.post(f"/finance/funds/{req['id']}/finish-check", headers=ana).status_code == 409
    assert client.get(f"/finance/funds/{req['id']}", headers=ben).json()["status"] == "to_check"
    # An admin gives it its account back, and the review completes.
    account = next(a for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"] if a["code"] == "6200")
    fixed = client.put(
        f"/finance/funds/categories/{transport['id']}",
        json={"name": "Transportation", "accountId": account["id"], "reimbursable": True, "isActive": True},
        headers=ana,
    )
    assert fixed.status_code == 200, fixed.text
    assert finish(client, ana, req["id"])["status"] == "to_return"


def test_liquidation_is_due_in_a_week_and_late_ones_are_flagged(app, client, ben):
    req = release(client, ben, approved(client)["id"])
    assert req["release"]["liquidateBy"] == (manila_today() + timedelta(days=7)).isoformat()
    assert req["overdue"] is False
    # Someone else's, so it's only the date that's wrong (Rico has req-1 to liquidate).
    other = approved(client, "req-2", requester=("Lia Cruz", "lia@example.com"))
    past = client.post(
        f"/finance/funds/{other['id']}/release",
        json={"amountCentavos": 500000, "method": "cash", "liquidateBy": (manila_today() - timedelta(days=2)).isoformat()},
        headers=ben,
    )
    assert past.status_code == 422
    # Two days past its due date, and still not liquidated.
    with app.state.sessions() as db:
        db.get(FundRequest, req["id"]).liquidate_by = manila_today() - timedelta(days=2)
        db.commit()
    assert client.get("/finance/funds/counts", headers=ben).json()["overdue"] == 1
    listed = client.get("/finance/funds", params={"task": "to_liquidate"}, headers=ben).json()["items"]
    assert [(r["id"], r["overdue"]) for r in listed] == [(req["id"], True)]


def test_receipts_refused_at_the_door(client, ben):
    req = release(client, ben, approved(client)["id"])
    food = categories(client)["Food"]
    base = {"spentOn": manila_today().isoformat(), "description": "Dinner", "categoryId": food["id"], "amountCentavos": 1000, "by": "Rico"}

    def send(**extra):
        return client.post("/integration/funds/requests/req-1/expenses", json={**base, **extra}, headers=KEY)

    assert send().status_code == 422  # no receipt, and no reason why
    assert send(receipt={"name": "notes.txt", "contentType": "text/plain", "data": PNG}).status_code == 422
    assert send(receipt={"name": "r.png", "contentType": "image/png", "data": "not base64!"}).status_code == 422
    too_big = base64.b64encode(b"0" * (4 * 1024 * 1024 + 1)).decode()
    assert send(receipt={"name": "big.png", "contentType": "image/png", "data": too_big}).status_code == 422
    later = (manila_today() + timedelta(days=2)).isoformat()
    assert send(spentOn=later, noReceiptReason="Jeepney fare").status_code == 422
    assert client.get(f"/finance/funds/{req['id']}", headers=ben).json()["expenses"] == []


def test_each_step_only_in_its_turn(client, ben):
    req = release(client, ben, approved(client)["id"])
    base = f"/finance/funds/{req['id']}"
    assert client.post(f"{base}/release", json={"amountCentavos": 1000, "method": "cash"}, headers=ben).status_code == 409
    assert client.post(f"{base}/cancel", json={"reason": "Changed my mind"}, headers=ben).status_code == 409
    assert client.post(f"{base}/send-back", json={"note": "Too early"}, headers=ben).status_code == 409
    assert client.post(f"{base}/finish-check", headers=ben).status_code == 409
    assert client.post(f"{base}/returned", json={"amountCentavos": 1000}, headers=ben).status_code == 409
    assert client.post(f"{base}/reimbursed", json={"amountCentavos": 1000}, headers=ben).status_code == 409
    # And an app's key isn't a Finance sign-in.
    assert client.get("/finance/funds", headers=KEY).status_code == 401


@pytest.fixture
def two_apps(tmp_path):
    attempts.clear()
    settings = Settings(
        _env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{(tmp_path / 'two.db').as_posix()}",
        integration_keys=[f"crm:{CRM_KEY}", f"pharmacy:{PHARMACY_KEY}"],
    )
    with TestClient(create_app(settings)) as c:
        yield c


def test_two_apps_requests_never_meet(two_apps):
    from_crm = approved(two_apps)
    pharmacy = {"X-Nabhi-Key": PHARMACY_KEY}
    # The same id from another app is not the CRM's request.
    assert two_apps.get("/integration/funds/requests/req-1", headers=pharmacy).status_code == 404
    assert two_apps.get("/integration/funds/requests", params={"ids": "req-1"}, headers=pharmacy).json()["items"] == {}
    body = {
        "sourceId": "req-1", "number": "PH-0001", "requesterName": "Nena Gutierrez", "requesterEmail": "nena@example.com",
        "purpose": "Supplies", "liquidate": True, "requestedCentavos": 10000, "approvedCentavos": 10000,
        "approvedByName": "Vicky Ong", "approvedAt": datetime.now(ZoneInfo("UTC")).isoformat(),
    }
    theirs = two_apps.post("/integration/funds/requests", json=body, headers=pharmacy).json()
    assert theirs["id"] != from_crm["id"] and theirs["sourceApp"] == "pharmacy"
    assert two_apps.get("/integration/funds/requests/req-1", headers=KEY).json()["number"] == from_crm["number"]
