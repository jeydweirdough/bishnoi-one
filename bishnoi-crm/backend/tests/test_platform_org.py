"""The org chart from Bishnoi One Platform (app/platform_org.py, feature plan step 4): the CRM's
teams are a copy of the Platform's units, with the same ids, and people sit where the Platform says."""

import time

import pytest
from sqlalchemy import func, select

from app import platform_org
from app.models import Team, User
from tests.test_platform_roles import WHO, database, note
from tests.test_platform_sign_in import linked  # noqa: F401 (fixture)

HOS, FIELD, DEEP, TRAIN = (f"22222222-0000-4000-8000-00000000000{i}" for i in range(1, 5))
UNITS = [
    {"id": FIELD, "kind": "team", "name": "Field NCR 1", "parentId": HOS, "manager": WHO, "areas": ["Commonwealth"], "active": True},
    {"id": HOS, "kind": "division", "name": "HOS", "parentId": None, "manager": None, "areas": ["Cebu"], "active": True},
    {"id": DEEP, "kind": "team", "name": "Field NCR 1 East", "parentId": FIELD, "manager": None, "areas": [], "active": True},
    {"id": TRAIN, "kind": "department", "name": "Training", "parentId": None, "manager": None, "areas": [], "active": False},
]


@pytest.fixture(autouse=True)
def fresh():
    platform_org._newest.clear()


def test_the_chart_becomes_the_teams_and_people_sit_where_the_platform_says(app, client, linked):
    r = client.post("/platform/organisation", json={"pass": note("organisation", units=UNITS, people=[{"email": WHO, "unit": FIELD, "otherUnits": [HOS]}])})
    assert r.status_code == 204, r.text
    with database(app)() as db:
        teams = {t.id: t for t in db.scalars(select(Team))}
        assert teams[HOS].parent_id is None and teams[FIELD].parent_id == HOS
        assert teams[DEEP].parent_id == HOS  # one level here: under the division at the top
        assert teams[FIELD].headquarters == ["Commonwealth"] and not teams[TRAIN].is_active
        ben = db.scalar(select(User).where(func.lower(User.email) == WHO))
        assert teams[FIELD].manager_id == ben.id
        assert ben.team_id == FIELD and [t.id for t in ben.other_teams] == [HOS]

    # Renamed on the Platform: renamed here, the same team; an older note isn't taken.
    time.sleep(1)
    renamed = [{**u, "name": "Hospitals"} if u["id"] == HOS else u for u in UNITS]
    assert client.post("/platform/organisation", json={"pass": note("organisation", units=renamed)}).status_code == 204
    with database(app)() as db:
        assert db.get(Team, HOS).name == "Hospitals"


def test_a_note_of_another_kind_is_refused(client, linked):
    assert client.post("/platform/organisation", json={"pass": note("roles", units=UNITS)}).status_code == 404


def test_once_connected_teams_are_arranged_on_the_platform(app, client):
    app.state.settings.platform_api_url = "http://platform.test"
    try:
        assert client.post("/admin/teams", json={"name": "New team"}).status_code == 409
        assert client.delete("/admin/teams/x").status_code == 409
        assert client.patch("/admin/teams/x", json={"parentId": None}).status_code == 409
        assert client.patch("/admin/users/x", json={"teamId": "t"}).status_code == 409
        # What is the CRM's own about a team still changes here.
        assert client.patch("/admin/teams/x", json={"description": "Hospitals"}).status_code != 409
    finally:
        app.state.settings.platform_api_url = None


def test_finance_is_given_the_salespersons_team_and_division(app, client, linked):
    """Each invoice keeps its salesperson's division and team (Finance migration 0025)."""
    from app.routers.integration import owner_out

    client.post("/platform/organisation", json={"pass": note("organisation", units=UNITS, people=[{"email": WHO, "unit": FIELD}])})
    with database(app)() as db:
        ben = db.scalar(select(User).where(func.lower(User.email) == WHO))
        assert owner_out(ben)["team"] == {"id": FIELD, "name": "Field NCR 1"}
        assert owner_out(ben)["division"] == {"id": HOS, "name": "HOS"}
        ben.team_id = HOS
        db.flush()
        db.refresh(ben)
        assert owner_out(ben)["team"] is None and owner_out(ben)["division"]["name"] == "HOS"


def test_the_org_chart_arrives_as_a_business_event_once(app, client, linked):
    """Feature plan step 7: the Platform sends the chart as the event "organisation.changed"."""
    from app.business_events import InboxEvent

    event = {"id": "ev-22222222", "kind": "organisation.changed", "source": "platform",
             "data": {"units": UNITS, "people": [{"email": WHO, "unit": FIELD, "otherUnits": []}]}, "occurredAt": "2026-10-28T00:00:00+00:00"}
    for _ in range(2):
        r = client.post("/platform/events", json={"pass": note("event", event=event)})
        assert r.status_code == 204, r.text
    with database(app)() as db:
        assert db.get(Team, FIELD).parent_id == HOS
        assert db.scalar(select(User).where(func.lower(User.email) == WHO)).team_id == FIELD
        assert db.get(InboxEvent, "ev-22222222").kind == "organisation.changed"
