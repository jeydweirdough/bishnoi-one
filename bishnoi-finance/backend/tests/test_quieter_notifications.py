"""Fewer notifications and approvals (decided 2026-10-22: Plans/Plan - Fewer
notifications and approvals):

1. once someone acts, everyone's notification about it is done;
2. several of a kind are one line, and only what needs you counts;
3. the Finance Head is told first (journal.first); the Deputy is backup, told of
   the Head's own entries and of ones still waiting after a working day;
4. several entries approved at once, each checked as if alone.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import JournalEntry

from .test_dashboard import DEPUTY, HEAD, BIR, person
from .test_funds import approved, release
from .test_journal_approval import bell, post
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)

APPROVE = ["journal.approve"]


@pytest.fixture
def malou(client, ana):
    return person(client, ana, "Finance Head", HEAD + APPROVE + ["journal.first"])


@pytest.fixture
def cristal(client, ana):
    return person(client, ana, "Finance Deputy", DEPUTY + APPROVE)


@pytest.fixture
def rommel(client, ana):
    return person(client, ana, "BIR and Compliance", BIR)


def kinds(client, who) -> list[str]:
    return [i["kind"] for i in bell(client, who)["items"] if not i["read"]]


def test_the_head_is_told_first_and_the_deputy_only_of_the_heads_own(client, ana, malou, cristal, rommel):
    post(client, rommel)
    assert kinds(client, malou) == ["entry.waiting"]
    assert kinds(client, cristal) == []  # backup: not told yet
    assert bell(client, ana)["unread"] == 0  # the Administrator (IT) isn't anyone's first approver
    post(client, malou, memo="Malou's own")
    assert kinds(client, cristal) == ["entry.waiting"]  # Malou can't approve her own: Cristal is told


def test_the_deputy_is_told_once_an_entry_waited_a_working_day(app, client, malou, cristal, rommel):
    e = post(client, rommel)
    with app.state.sessions() as db:
        # Posted on a Monday 9:00 Manila time, a week ago: well past a working day.
        db.get(JournalEntry, e["id"]).created_at = datetime(2026, 10, 12, 1, 0, tzinfo=UTC)
        db.commit()
    n = bell(client, cristal)
    assert n["unread"] == 1 and n["items"][0]["text"].startswith("Still waiting after a working day: BIR and Compliance posted")
    # Asked again, it isn't repeated.
    assert bell(client, cristal)["unread"] == 1 and len(bell(client, cristal)["items"]) == 1


def test_not_yet_a_working_day_later(app, client, malou, cristal, rommel):
    e = post(client, rommel)
    with app.state.sessions() as db:
        db.get(JournalEntry, e["id"]).created_at = datetime.now(UTC) - timedelta(hours=2)
        db.commit()
    assert bell(client, cristal)["unread"] == 0  # posted two hours ago: Malou's to see first
    # (When "a working day later" falls, Sundays and holidays skipped: tests/test_workdays.py.)


def test_acting_clears_everyones_notification(client, ana, malou, cristal, rommel):
    # Malou's own entry: she can't approve it, so everyone else who may approve is told (Cristal, Ana).
    e = post(client, malou, memo="Malou's own")
    assert kinds(client, cristal) == ["entry.waiting"] and kinds(client, ana) == ["entry.waiting"]
    client.post(f"/finance/ledger/entries/{e['id']}/approve", headers=cristal)
    assert kinds(client, ana) == []  # Cristal decided it: nothing left for the Administrator
    # Marketing requests: released by one, the others' "to release" is done.
    req = approved(client)
    assert "fund.to_release" in kinds(client, ana) and "fund.to_release" in kinds(client, cristal)
    release(client, cristal, req["id"])
    assert "fund.to_release" not in kinds(client, ana)


def test_only_what_needs_you_counts(client, malou, rommel):
    e = post(client, rommel)
    client.post(f"/finance/ledger/entries/{e['id']}/approve", headers=malou)
    n = bell(client, rommel)
    assert n["unread"] == 0 and n["items"][0]["kind"] == "entry.approved" and not n["items"][0]["counts"]
    r = post(client, rommel, memo="Accrual")
    client.post(f"/finance/ledger/entries/{r['id']}/reject", json={"reason": "Wrong month"}, headers=malou)
    assert bell(client, rommel)["unread"] == 1  # a rejection asks something of him: it counts


def test_approve_several_at_once(client, malou, cristal, rommel):
    a, b, c = (post(client, rommel, memo=m) for m in ("One", "Two", "Three"))
    mine = post(client, malou, memo="Malou's own")
    client.post(f"/finance/ledger/entries/{c['id']}/approve", headers=cristal)  # decided a moment before
    r = client.post("/finance/ledger/entries/approve", json={"ids": [a["id"], b["id"], c["id"], mine["id"]]}, headers=malou).json()
    assert r["approved"] == [a["number"], b["number"]]
    skipped = {s["number"]: s["reason"] for s in r["skipped"]}
    assert skipped[c["number"]].startswith("Finance Deputy already approved")
    assert skipped[mine["number"]] == "You posted this entry, so someone else approves it."
    assert client.post("/finance/ledger/entries/approve", json={"ids": [a["id"]]}, headers=rommel).status_code == 403


def test_a_reversal_still_waiting_is_said_so(client, malou, cristal, rommel):
    e = post(client, rommel)
    client.post(f"/finance/ledger/entries/{e['id']}/approve", headers=malou)
    back = client.post(f"/finance/ledger/entries/{e['id']}/reverse", json={}, headers=malou).json()
    listed = next(i for i in client.get("/finance/ledger/entries", headers=rommel).json()["items"] if i["id"] == e["id"])
    assert listed["reversalStatus"] == "waiting"
    client.post(f"/finance/ledger/entries/{back['id']}/approve", headers=cristal)
    assert client.get(f"/finance/ledger/entries/{e['id']}", headers=rommel).json()["reversalStatus"] == "approved"
