"""The calendar (decided 2026-10-22: Plans/Plan - Finance calendar): switched on per
person by an Administrator; each person's events are their own unless shared; repeats;
reminders in the bell and on the Overview, some working days before; done for everyone."""

from datetime import date, timedelta

import pytest

from app.calendar_events import occurrences
from app.models import CalendarEvent

from .test_dashboard import BIR, DEPUTY, HEAD, person
from .test_funds import approved, release
from .test_journal_approval import bell
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)


def user_id(client, ana, email: str) -> str:
    return next(u["id"] for u in client.get("/admin/users", headers=ana).json()["items"] if u["email"] == email)


def switch(client, ana, email: str, on: bool = True):
    r = client.patch(f"/admin/users/{user_id(client, ana, email)}", json={"calendarOn": on}, headers=ana)
    assert r.status_code == 200 and r.json()["calendarOn"] is on, r.text
    return r


@pytest.fixture
def malou(client, ana):
    who = person(client, ana, "Finance Head", HEAD)
    switch(client, ana, "finance.head@example.com")
    return who


@pytest.fixture
def cristal(client, ana):
    who = person(client, ana, "Finance Deputy", DEPUTY)
    switch(client, ana, "finance.deputy@example.com")
    return who


@pytest.fixture
def rommel(client, ana):
    who = person(client, ana, "BIR and Compliance", BIR)
    switch(client, ana, "bir.and.compliance@example.com")
    return who


def add(client, who, **body) -> dict:
    body = {"title": "2550Q", "startsOn": date.today().isoformat()} | body
    r = client.post("/finance/calendar/events", json=body, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def titles(client, who, **params) -> list[str]:
    return [i["event"]["title"] for i in client.get("/finance/calendar", params=params, headers=who).json()["items"]]


def test_it_is_off_until_an_administrator_switches_it_on(client, ana, ben):
    assert client.get("/finance/calendar", headers=ben).status_code == 403
    me = client.get("/auth/me", headers=ben).json()
    assert "calendar.use" not in me["permissions"]
    switch(client, ana, "ben@example.com")
    assert client.get("/finance/calendar", headers=ben).status_code == 200
    assert "calendar.use" in client.get("/auth/me", headers=ben).json()["permissions"]
    # Not given with a role, the Administrator's included.
    assert client.get("/finance/calendar", headers=ana).status_code == 403
    assert client.post("/admin/roles", json={"name": "Calendar for all", "permissions": ["calendar.use"]}, headers=ana).status_code == 422
    # Only someone who manages users switches it.
    assert client.patch(f"/admin/users/{user_id(client, ana, 'ben@example.com')}", json={"calendarOn": False}, headers=ben).status_code == 403


def test_switching_it_on_tells_the_person(client, ana, ben):
    switch(client, ana, "ben@example.com")
    n = bell(client, ben)
    assert n["items"][0]["kind"] == "calendar.on" and n["unread"] == 0  # news: not counted


def test_each_calendar_is_its_own_unless_shared(client, ana, malou, rommel, ben):
    add(client, rommel, title="1601-C for October")
    assert titles(client, rommel) == ["1601-C for October"]
    assert titles(client, malou) == []
    shared = add(client, rommel, title="2550Q for Q3", sharedWith=[user_id(client, ana, "finance.head@example.com")])
    assert titles(client, malou) == ["2550Q for Q3"]
    n = bell(client, malou)
    assert n["items"][0]["kind"] == "calendar.shared" and "BIR and Compliance shared “2550Q for Q3”" in n["items"][0]["text"]
    # Only with people who have the calendar.
    r = client.post("/finance/calendar/events", json={"title": "X", "startsOn": date.today().isoformat(), "sharedWith": [user_id(client, ana, "ben@example.com")]}, headers=rommel)
    assert r.status_code == 422
    # Only the owner changes or removes it; others don't even see unshared ones.
    body = {"title": "Changed", "startsOn": date.today().isoformat()}
    assert client.put(f"/finance/calendar/events/{shared['id']}", json=body, headers=malou).status_code == 403
    assert client.delete(f"/finance/calendar/events/{shared['id']}", headers=malou).status_code == 403
    mine = add(client, malou, title="Malou's own")
    assert client.put(f"/finance/calendar/events/{mine['id']}", json=body, headers=rommel).status_code == 404
    # Links stay inside Finance.
    assert client.post("/finance/calendar/events", json={**body, "link": "https://example.com"}, headers=malou).status_code == 422


def test_repeats():
    e = CalendarEvent(title="t", starts_on=date(2026, 1, 31), repeat="monthly")
    assert occurrences(e, date(2026, 1, 1), date(2026, 4, 30)) == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]
    e = CalendarEvent(title="t", starts_on=date(2026, 10, 1), repeat="twice_monthly", until=date(2026, 11, 20))
    assert occurrences(e, date(2026, 10, 1), date(2026, 12, 31)) == [date(2026, 10, 15), date(2026, 10, 31), date(2026, 11, 15)]
    e = CalendarEvent(title="t", starts_on=date(2026, 1, 25), repeat="quarterly")
    assert occurrences(e, date(2026, 1, 1), date(2026, 12, 31)) == [date(2026, 1, 25), date(2026, 4, 25), date(2026, 7, 25), date(2026, 10, 25)]
    e = CalendarEvent(title="t", starts_on=date(2026, 4, 15), repeat="none")
    assert occurrences(e, date(2026, 5, 1), date(2026, 5, 31)) == []


def test_a_reminder_comes_once_and_done_clears_it_for_everyone(client, ana, malou, rommel):
    e = add(client, rommel, title="SLSP Sales DAT", remindDays=0, sharedWith=[user_id(client, ana, "finance.head@example.com")])
    for who in (rommel, malou):
        n = bell(client, who)
        assert n["unread"] >= 1 and any(i["kind"] == "calendar.reminder" and i["text"].startswith("SLSP Sales DAT: today") for i in n["items"])
    assert sum(i["kind"] == "calendar.reminder" for i in bell(client, rommel)["items"]) == 1  # not repeated
    today = date.today().isoformat()
    r = client.post(f"/finance/calendar/events/{e['id']}/done", json={"on": today}, headers=malou)
    assert r.status_code == 200 and r.json()["done"]["by"] == "Finance Head"
    assert client.post(f"/finance/calendar/events/{e['id']}/done", json={"on": today}, headers=rommel).status_code == 200  # already done: fine
    for who in (rommel, malou):
        assert not [i for i in bell(client, who)["items"] if i["kind"] == "calendar.reminder" and not i["read"]]
    assert any(i["kind"] == "calendar.done" for i in bell(client, rommel)["items"])  # the owner hears Malou did it
    # A date it doesn't fall on can't be done.
    assert client.post(f"/finance/calendar/events/{e['id']}/done", json={"on": (date.today() + timedelta(days=1)).isoformat()}, headers=rommel).status_code == 422


def test_a_reminder_some_working_days_before_waits_until_then(client, rommel):
    add(client, rommel, title="Far off", startsOn=(date.today() + timedelta(days=30)).isoformat(), remindDays=3)
    assert not [i for i in bell(client, rommel)["items"] if i["kind"] == "calendar.reminder"]


def test_the_overview_shows_whats_coming(client, ana, malou):
    add(client, malou, title="Bank reconciliation", startsOn=(date.today() + timedelta(days=2)).isoformat())
    sections = {s["key"]: s for s in client.get("/finance/dashboard", headers=malou).json()["sections"]}
    assert [i["title"] for i in sections["coming"]["items"]] == ["Bank reconciliation"]


def test_the_month_shows_holidays_and_liquidations_due(client, ana, ben, cristal):
    data = client.get("/finance/calendar", params={"from": "2026-12-01", "to": "2026-12-31"}, headers=cristal).json()
    assert {"on": "2026-12-25", "name": "Christmas Day"} in data["holidays"]
    r = release(client, ben, approved(client)["id"])
    due = client.get("/finance/calendar", headers=cristal, params={"from": date.today().isoformat(), "to": (date.today() + timedelta(days=30)).isoformat()}).json()["liquidations"]
    assert [d["id"] for d in due] == [r["id"]]
