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


def test_a_unit_head_reaches_its_children_even_without_reporting_links(app, client, linked):
    from app.access import access_of
    from app.models import Role
    from app.scope import reachable_people

    with database(app)() as db:
        role = db.scalar(select(Role).where(Role.name == "Salesperson"))
        db.add(User(email="sam@example.com", full_name="Sam", password_hash="hash", role_id=role.id))
        db.commit()

    div_id = "33333333-0000-4000-8000-000000000001"
    sub_id = "33333333-0000-4000-8000-000000000002"
    units = [
        {"id": div_id, "kind": "division", "name": "Rx Business", "parentId": None, "manager": WHO, "areas": [], "active": True},
        {"id": sub_id, "kind": "team", "name": "B2C Team", "parentId": div_id, "manager": None, "areas": [], "active": True},
    ]
    people = [
        {"email": WHO, "unit": div_id, "otherUnits": []},
        {"email": "sam@example.com", "unit": sub_id, "otherUnits": []},
    ]
    linked = [dict(people[0]), {**people[1], "reportsTo": WHO}]
    r = client.post("/platform/organisation", json={"pass": note("organisation", units=units, people=people)})
    assert r.status_code == 204, r.text
    with database(app)() as db:
        mgr = db.scalar(select(User).where(func.lower(User.email) == WHO))
        sam = db.scalar(select(User).where(func.lower(User.email) == "sam@example.com"))
        # sub team inherited manager
        assert db.get(Team, sub_id).manager_id == mgr.id
        # sub team is under division
        assert db.get(Team, sub_id).parent_id == div_id
        # mgr with managed role reaches sam
        mgr.role = db.scalar(select(User).where(User.email == "mia@example.com")).role if db.scalar(select(User).where(User.email == "mia@example.com")) else mgr.role
        # Set mgr to Manager role (scope = managed)
        from app.models import Role
        mgr.role = db.scalar(select(Role).where(Role.name == "Manager"))
        db.flush()
        access = access_of(mgr)
        reached = reachable_people(db, access)
        # The authoritative org-chart head reaches this child team even without individual reporting links.
        assert sam in reached
    assert client.post("/platform/organisation", json={"pass": note("organisation", units=units, people=linked)}).status_code == 204
    with database(app)() as db:
        mgr = db.scalar(select(User).where(func.lower(User.email) == WHO))
        sam = db.scalar(select(User).where(func.lower(User.email) == "sam@example.com"))
        mgr.role = db.scalar(select(Role).where(Role.name == "Manager"))
        db.flush()
        assert sam.reports_to_id == mgr.id
        assert sam in reachable_people(db, access_of(mgr))
        # Removing a reporting link does not revoke the separate org-head assignment.
    assert client.post("/platform/organisation", json={"pass": note("organisation", units=units, people=people_plain(people))}).status_code == 204
    with database(app)() as db:
        mgr = db.scalar(select(User).where(func.lower(User.email) == WHO))
        sam = db.scalar(select(User).where(func.lower(User.email) == "sam@example.com"))
        mgr.role = db.scalar(select(Role).where(Role.name == "Manager"))
        db.flush()
        assert sam.reports_to_id is None and sam in reachable_people(db, access_of(mgr))


def people_plain(people):
    return [{**p, "reportsTo": None, "assistantOf": None} for p in people]


def test_a_chain_of_links_reaches_to_any_depth_and_an_assistant_reaches_what_the_manager_does(app, client, linked):
    """Department > division > team (2026-11-03): the head of the department reaches the people three levels down."""
    from app.access import access_of
    from app.models import Role
    from app.scope import reachable_people

    with database(app)() as db:
        role = db.scalar(select(Role).where(Role.name == "Salesperson"))
        for who in ("mary", "lead", "sec"):
            db.add(User(email=f"{who}@example.com", full_name=who.title(), password_hash="hash", role_id=role.id))
        db.commit()
    dept, div, team = (f"44444444-0000-4000-8000-00000000000{n}" for n in (1, 2, 3))
    units = [
        {"id": dept, "kind": "department", "name": "Sales", "parentId": None, "manager": WHO, "areas": [], "active": True},
        {"id": div, "kind": "division", "name": "Prescription", "parentId": dept, "manager": None, "areas": [], "active": True},
        {"id": team, "kind": "team", "name": "B2C Rx", "parentId": div, "manager": None, "areas": [], "active": True},
    ]
    people = [
        {"email": WHO, "unit": dept, "otherUnits": []},
        {"email": "lead@example.com", "unit": div, "otherUnits": [], "reportsTo": WHO},
        {"email": "mary@example.com", "unit": team, "otherUnits": [], "reportsTo": "lead@example.com"},
        {"email": "sec@example.com", "unit": dept, "otherUnits": [], "assistantOf": WHO},
    ]
    assert client.post("/platform/organisation", json={"pass": note("organisation", units=units, people=people)}).status_code == 204
    with database(app)() as db:
        head = db.scalar(select(User).where(func.lower(User.email) == WHO))
        head.role = db.scalar(select(Role).where(Role.name == "Manager"))
        sec = db.scalar(select(User).where(User.email == "sec@example.com"))
        sec.role = db.scalar(select(Role).where(Role.name == "Salesperson"))  # her own role: only her own records
        db.flush()
        reached = {u.email for u in reachable_people(db, access_of(head))}
        assert {"mary@example.com", "lead@example.com"} <= reached  # two levels down, through the lead
        # The assistant reaches what the manager reaches, though her role alone reaches only herself.
        assert {"mary@example.com", "lead@example.com"} <= {u.email for u in reachable_people(db, access_of(sec))}
        assert access_of(sec).scope == "managed" and "update" not in access_of(sec).permissions


def test_the_chart_event_sets_who_reports_to_whom(app, client, linked):
    """The chart reaches the CRM as an event (business_events), not only as a signed note: both set the links."""
    from app import business_events
    from app.models import Role

    with database(app)() as db:
        role = db.scalar(select(Role).where(Role.name == "Salesperson"))
        db.add(User(email="ed@example.com", full_name="Ed", password_hash="hash", role_id=role.id))
        db.commit()
        data = {"units": [], "people": [{"email": "ed@example.com", "unit": None, "otherUnits": [], "reportsTo": WHO, "assistantOf": None}]}
        business_events._organisation(db, data, "example")
        db.commit()
        boss = db.scalar(select(User).where(func.lower(User.email) == WHO))
        ed = db.scalar(select(User).where(User.email == "ed@example.com"))
        assert ed.reports_to_id == boss.id
