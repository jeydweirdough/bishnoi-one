"""Journal entries typed by hand wait for approval, and Finance's notifications
(decided 2026-10-22: Plans/Plan - Journal approval and notifications).

- An entry typed by hand (or a reversal) counts only once someone who may approve
  entries, never whoever posted it, approves it. A rejected one never counts.
- Entries a marketing request or an invoice makes count at once.
- Two approvers clicking at nearly the same moment: the first wins, the second is
  told who decided, and nothing else changes.
- Notifications go by permission, never to whoever acted.
"""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import JournalEntry, User
from app.routers.ledger import decide

from .test_dashboard import DEPUTY, HEAD, BIR, person
from .test_funds import KEY, approved, categories, check_all, release, spend
from .test_ledger import accounts
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)

APPROVER_HEAD = HEAD + ["journal.approve"]
APPROVER_DEPUTY = DEPUTY + ["journal.approve"]


@pytest.fixture
def malou(client, ana):
    return person(client, ana, "Finance Head", APPROVER_HEAD)


@pytest.fixture
def cristal(client, ana):
    return person(client, ana, "Finance Deputy", APPROVER_DEPUTY)


@pytest.fixture
def rommel(client, ana):
    return person(client, ana, "BIR and Compliance", BIR)


def post(client, who, amount=1200000, memo="Depreciation, October") -> dict:
    acc = accounts(client, who)
    body = {"date": date.today().isoformat(), "memo": memo, "lines": [
        {"accountId": acc["6900"]["id"], "debitCentavos": amount},
        {"accountId": acc["1010"]["id"], "creditCentavos": amount},
    ]}
    r = client.post("/finance/ledger/entries", json=body, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def bell(client, who) -> dict:
    return client.get("/finance/notifications", headers=who).json()


def counted(client, who) -> dict[str, int]:
    tb = client.get("/finance/ledger/trial-balance", headers=who).json()
    return {r["account"]["code"]: r["balanceCentavos"] for r in tb["rows"]} | {"waiting": tb["waiting"]}


def test_an_entry_typed_by_hand_waits_and_counts_once_approved(client, malou, cristal, rommel):
    e = post(client, rommel)
    assert e["status"] == "waiting" and e["canDecide"] is False  # not his to decide
    assert counted(client, rommel) == {"waiting": 1}  # not in the books yet
    # Malou and Cristal are told; Rommel, who posted it, isn't.
    for approver in (malou, cristal):
        n = bell(client, approver)
        assert n["unread"] == 1 and n["items"][0]["kind"] == "entry.waiting"
        assert "Waiting for your approval" in n["items"][0]["text"] and n["items"][0]["link"].startswith("/ledger?q=JE-")
    assert bell(client, rommel)["unread"] == 0
    # Malou sees it on her Overview; Rommel sees his side of the hand-off.
    waiting = next(s for s in client.get("/finance/dashboard", headers=malou).json()["sections"] if s["key"] == "waiting")
    assert waiting["canApproveEntries"] and waiting["entriesToApprove"] == 1
    assert client.get(f"/finance/ledger/entries/{e['id']}", headers=malou).json()["canDecide"] is True

    done = client.post(f"/finance/ledger/entries/{e['id']}/approve", headers=malou)
    assert done.status_code == 200 and done.json()["status"] == "approved" and done.json()["decidedBy"] == "Finance Head"
    assert counted(client, rommel) == {"1010": -1200000, "6900": 1200000, "waiting": 0}
    told = bell(client, rommel)["items"][0]
    assert told["kind"] == "entry.approved" and "now counts in the books" in told["text"]


def test_nobody_approves_their_own_entry(client, malou, cristal):
    mine = post(client, malou)
    assert mine["canDecide"] is False
    refused = client.post(f"/finance/ledger/entries/{mine['id']}/approve", headers=malou)
    assert refused.status_code == 403 and "someone else approves it" in refused.json()["detail"]
    # Malou's own entries go to Cristal.
    assert bell(client, cristal)["unread"] == 1 and bell(client, malou)["unread"] == 0
    assert client.post(f"/finance/ledger/entries/{mine['id']}/approve", headers=cristal).status_code == 200


def test_two_approvers_at_once_the_first_wins_and_the_second_is_told(app, client, malou, cristal, rommel):
    e = post(client, rommel)
    with app.state.sessions() as cristals_page:
        # Cristal's page loaded the entry while it was waiting...
        stale = cristals_page.get(JournalEntry, e["id"])
        assert stale.status == "waiting"
        # ...then Malou approved it, a moment before Cristal clicked.
        assert client.post(f"/finance/ledger/entries/{e['id']}/approve", headers=malou).status_code == 200
        her = cristals_page.scalar(select(User).where(User.email == "finance.deputy@example.com"))
        with pytest.raises(HTTPException) as late:
            decide(cristals_page, app.state.settings, her, e["id"], "rejected", "Wrong account")
    assert late.value.status_code == 409
    assert late.value.detail.startswith("Finance Head already approved this entry at ") and late.value.detail.endswith("Nothing else was changed.")
    # Nothing changed: still Malou's approval, no reason, and it counts.
    now = client.get(f"/finance/ledger/entries/{e['id']}", headers=rommel).json()
    assert (now["status"], now["decidedBy"], now["rejectedReason"]) == ("approved", "Finance Head", None)
    # Clicking again through the API, or a double click by Malou, gets the same plain answer.
    again = client.post(f"/finance/ledger/entries/{e['id']}/approve", headers=cristal)
    assert again.status_code == 409 and again.json()["detail"].startswith("Finance Head already approved")
    mine = client.post(f"/finance/ledger/entries/{e['id']}/approve", headers=malou)
    assert mine.status_code == 409 and mine.json()["detail"].startswith("You already approved")
    # Rommel was told once.
    assert [n["kind"] for n in bell(client, rommel)["items"]] == ["entry.approved"]


def test_a_rejected_entry_never_counts_and_the_poster_is_told_why(client, malou, rommel):
    e = post(client, rommel)
    blank = client.post(f"/finance/ledger/entries/{e['id']}/reject", json={"reason": "   "}, headers=malou)
    assert blank.status_code == 422
    r = client.post(f"/finance/ledger/entries/{e['id']}/reject", json={"reason": "Wrong account: use 6100"}, headers=malou).json()
    assert (r["status"], r["rejectedReason"]) == ("rejected", "Wrong account: use 6100")
    assert counted(client, rommel) == {"waiting": 0}
    told = bell(client, rommel)["items"][0]
    assert told["kind"] == "entry.rejected" and told["text"].endswith("Wrong account: use 6100")
    # It stays in the journal, marked; it can't be approved afterwards or reversed.
    assert client.get("/finance/ledger/entries", params={"status": "rejected"}, headers=rommel).json()["items"][0]["id"] == e["id"]
    assert client.post(f"/finance/ledger/entries/{e['id']}/approve", headers=malou).status_code == 409
    assert client.post(f"/finance/ledger/entries/{e['id']}/reverse", json={}, headers=malou).status_code == 409


def test_a_reversal_waits_too_and_a_rejected_one_frees_the_entry(client, malou, cristal, rommel):
    e = post(client, rommel)
    client.post(f"/finance/ledger/entries/{e['id']}/approve", headers=malou)
    # Waiting entries can't be reversed: they're rejected instead.
    pending = post(client, rommel, memo="Accrual")
    assert client.post(f"/finance/ledger/entries/{pending['id']}/reverse", json={}, headers=malou).status_code == 409
    back = client.post(f"/finance/ledger/entries/{e['id']}/reverse", json={}, headers=malou).json()
    assert back["status"] == "waiting"
    assert counted(client, rommel)["6900"] == 1200000  # the reversal doesn't count yet
    client.post(f"/finance/ledger/entries/{back['id']}/reject", json={"reason": "Not needed"}, headers=cristal)
    # The entry can be reversed again, and this time it's approved.
    again = client.post(f"/finance/ledger/entries/{e['id']}/reverse", json={}, headers=malou).json()
    assert client.post(f"/finance/ledger/entries/{again['id']}/approve", headers=cristal).status_code == 200
    assert counted(client, rommel).get("6900", 0) == 0


def test_automatic_entries_count_at_once(client, ben, malou):
    release(client, ben, approved(client)["id"])
    entries = client.get("/finance/ledger/entries", headers=malou).json()["items"]
    assert [e["status"] for e in entries] == ["approved"]
    assert counted(client, malou)["1200"] == 500000  # the advance is in the books straight away


def test_marketing_requests_tell_whoever_does_the_next_step(client, ana, malou, cristal):
    # A request arrives: whoever may release is told (Cristal; the Administrator too).
    req = approved(client)
    assert [n["kind"] for n in bell(client, cristal)["items"]] == ["fund.to_release"]
    assert bell(client, malou)["unread"] == 0  # she reviews, she doesn't release
    release(client, cristal, req["id"])
    spend(client, 320000, categories(client)["Food"])
    client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico Santos"}, headers=KEY)
    # The liquidation: reviewers are told, not Cristal who released it.
    assert bell(client, malou)["items"][0]["kind"] == "fund.to_check"
    assert "fund.to_check" not in [n["kind"] for n in bell(client, cristal)["items"]]
    sent = client.get(f"/finance/funds/{req['id']}", headers=malou).json()
    check_all(client, malou, sent)
    # Reviewed with unused funds to collect: whoever settles is told.
    top = bell(client, cristal)["items"][0]
    assert top["kind"] == "fund.to_settle" and "unused funds to collect from Rico Santos" in top["text"]


def test_each_person_reads_only_their_own_notifications(client, malou, cristal, rommel):
    post(client, rommel)
    post(client, rommel, memo="Accrual")
    n = bell(client, malou)
    assert n["unread"] == 2
    one = n["items"][0]["id"]
    # Cristal can't mark Malou's as read.
    client.post("/finance/notifications/read", json={"ids": [one]}, headers=cristal)
    assert bell(client, malou)["unread"] == 2
    after = client.post("/finance/notifications/read", json={"ids": [one]}, headers=malou).json()
    assert after["unread"] == 1 and next(i for i in after["items"] if i["id"] == one)["read"] is True
    assert client.post("/finance/notifications/read", json={}, headers=malou).json()["unread"] == 0
    assert bell(client, cristal)["unread"] == 2
    assert client.get("/finance/notifications").status_code == 401
