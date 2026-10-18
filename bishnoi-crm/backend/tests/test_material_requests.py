"""Promotional materials Admin gives out (app/routers/materials.py): Admin reads
the teams, asks, and the department's manager approves or rejects; Admin reads
the answer back and says when it was given out."""

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.models import Team, User
from tests.test_customers import crew  # noqa: F401 (a fixture)
from tests.test_managers import make_manager

KEY = "admin-key-that-is-long-enough-12345"
ADMIN = {"X-Bishnoi-Key": KEY}


@pytest.fixture
def linked(app):
    app.state.settings = app.state.settings.model_copy(update={"integration_keys": [SecretStr(f"exec:{KEY}")]})


def ids(app) -> dict[str, str]:
    with app.state.sessions() as db:
        out = {t.name: t.id for t in db.scalars(select(Team))}
        out |= {u.email.split("@")[0]: u.id for u in db.scalars(select(User))}
    return out


def ask(client, app, source_id="d-1", team="North", person=None, **changes) -> dict:
    known = ids(app)
    body = {
        "sourceId": source_id,
        "reference": "PD-40000001",
        "material": {"no": 40000001, "title": "Glucare leaflet", "kind": "Leaflet", "product": "Glucare 500 mg"},
        "teamId": known[team],
        "recipientId": known[person] if person else None,
        "quantity": 200,
        "purpose": "Doctor visits in October",
        "requestedBy": "Bea Navarro",
    }
    body.update(changes)
    return client.post("/integration/material-requests", json=body, headers=ADMIN)


def test_admin_reads_teams_with_their_manager_and_people(app, client, ana, crew, linked):
    assert client.get("/integration/teams").status_code == 401
    make_manager(app, client, ana, ["North"])
    teams = {t["name"]: t for t in client.get("/integration/teams", headers=ADMIN).json()["teams"]}
    assert teams["North"]["manager"]["name"] == "Mia"
    assert {p["name"] for p in teams["North"]["people"]} == {"Ria", "Rex", "Lia"}
    assert teams["South"]["manager"] is None


def test_the_manager_approves_only_their_own_teams(app, client, ana, crew, linked):
    mia = make_manager(app, client, ana, ["North"])
    r = ask(client, app, person="ria")
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "waiting"
    assert ask(client, app, "d-x", person="sam").status_code == 422  # Sam isn't in North
    ask(client, app, "d-2", team="South", quantity=50)

    # Mia sees North's request only; the salespeople see none.
    inbox = client.get("/material-requests", headers=mia).json()
    assert [(i["team"]["name"], i["recipient"]["name"]) for i in inbox["items"]] == [("North", "Ria")]
    assert inbox["counts"]["waiting"] == 1
    assert client.get("/material-requests", headers=crew["ria"]).status_code == 403
    south = next(i for i in client.get("/material-requests", headers=ana).json()["items"] if i["team"]["name"] == "South")
    assert client.post(f"/material-requests/{south['id']}/decision", json={"outcome": "approved"}, headers=mia).status_code == 404

    north = inbox["items"][0]
    r = client.post(f"/material-requests/{north['id']}/decision", json={"outcome": "approved", "note": "OK for October."}, headers=mia)
    assert r.status_code == 200, r.text
    answer = client.get("/integration/material-requests/d-1", headers=ADMIN).json()
    assert (answer["outcome"], answer["decidedBy"], answer["note"]) == ("approved", "Mia", "OK for October.")
    assert client.post(f"/material-requests/{north['id']}/decision", json={"outcome": "rejected", "note": "No."}, headers=mia).status_code == 409

    # The administrator decides South; a rejection says why.
    assert client.post(f"/material-requests/{south['id']}/decision", json={"outcome": "rejected"}, headers=ana).status_code == 422
    client.post(f"/material-requests/{south['id']}/decision", json={"outcome": "rejected", "note": "Too many this month."}, headers=ana)
    assert client.get("/integration/material-requests/d-2", headers=ADMIN).json()["outcome"] == "rejected"


def test_admin_says_when_it_was_given_out_or_cancelled(app, client, ana, crew, linked):
    mia = make_manager(app, client, ana, ["North"])
    ask(client, app)
    item = client.get("/material-requests", headers=mia).json()["items"][0]
    client.post(f"/material-requests/{item['id']}/decision", json={"outcome": "approved"}, headers=mia)
    # Sent again with a new quantity after the decision: the decision and what was approved stand.
    r = ask(client, app, quantity=999, state="distributed", distributedOn="2026-10-20")
    assert r.json()["outcome"] == "approved"
    item = client.get("/material-requests", headers=mia).json()["items"][0]
    assert (item["adminState"], item["distributedOn"], item["quantity"]) == ("distributed", "2026-10-20", 200)

    # Cancelled in Admin while waiting: it can't be decided any more.
    ask(client, app, "d-3")
    ask(client, app, "d-3", state="cancelled")
    waiting = next(i for i in client.get("/material-requests?status=waiting", headers=mia).json()["items"])
    assert waiting["adminState"] == "cancelled"
    assert client.post(f"/material-requests/{waiting['id']}/decision", json={"outcome": "approved"}, headers=mia).status_code == 409
    assert client.get("/integration/material-requests/nope", headers=ADMIN).status_code == 404
