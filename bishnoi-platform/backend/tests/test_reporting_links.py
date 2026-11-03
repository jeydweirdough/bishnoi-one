"""Reports to and assistant to (2026-11-03): links between people, checked, told to the apps, filled from the chart."""

from app import org_push
from app.models import Company, Identity
from app.tools.reporting_links import derive
from tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)


def link(client, h, who, **body):
    return client.put(f"/identity/access/people/{who['id']}/reporting", json=body, headers=h)


def test_links_are_set_checked_and_told_to_the_apps(app, client, getmeds):
    h, jade, rio, olive = getmeds["owner"]["h"], getmeds["jade"], getmeds["rio"], getmeds["owner"]
    assert link(client, h, jade, reportsToId=rio["id"]).json()["person"]["reportsToId"] == rio["id"]
    assert link(client, h, rio, reportsToId=olive["id"]).status_code == 200
    # No circles, nobody reports to themselves, an assistant isn't a boss, and a boss isn't an assistant.
    assert link(client, h, olive, reportsToId=jade["id"]).status_code == 422
    assert link(client, h, jade, reportsToId=jade["id"]).status_code == 422
    assert link(client, h, olive, assistantOfId=rio["id"]).status_code == 200
    assert link(client, h, jade, assistantOfId=olive["id"]).status_code == 422  # olive assists rio
    assert link(client, h, rio, assistantOfId=jade["id"]).status_code == 422  # rio has an assistant of their own
    # Someone who isn't an administrator can't set them.
    assert link(client, jade["h"], rio, reportsToId=olive["id"]).status_code == 403
    # What a pass says, and what the apps are told.
    with app.state.sessions() as db:
        person = db.get(Identity, jade["id"])
        assert org_push.manager_of(db, org_push._units(db, person.company_id), person) == "rio@getmeds.test"
        assert org_push.email_of(db, db.get(Identity, olive["id"]).assistant_of_id) == "rio@getmeds.test"
        chart = org_push.chart(db, db.get(Company, person.company_id))["people"]
        mine = next(p for p in chart if p["email"] == "jade@getmeds.test")
        assert mine["reportsTo"] == "rio@getmeds.test" and mine["assistantOf"] is None
        assert next(p for p in chart if p["email"] == "olive@getmeds.test")["assistantOf"] == "rio@getmeds.test"
    # Clearing one leaves the other alone.
    assert link(client, h, jade, reportsToId=None).json()["person"]["reportsToId"] is None
    assert link(client, h, olive).json()["person"]["assistantOfId"] == rio["id"]


def test_links_fill_from_the_heads_above_and_never_change_what_is_set(app, client, getmeds):
    h = getmeds["owner"]["h"]
    top = client.post("/identity/organisation/units", json={"kind": "division", "name": "Rx", "managerId": getmeds["owner"]["id"]}, headers=h).json()["unit"]
    team = client.post("/identity/organisation/units", json={"kind": "team", "name": "B2C", "parentId": top["id"], "managerId": getmeds["rio"]["id"]}, headers=h).json()["unit"]
    for who, unit in ((getmeds["jade"], team), (getmeds["rio"], team), (getmeds["owner"], top)):
        client.put(f"/identity/organisation/people/{who['id']}", json={"mainUnitId": unit["id"]}, headers=h)
    with app.state.sessions() as db:
        company = db.get(Company, db.get(Identity, getmeds["jade"]["id"]).company_id)
        got = {p.email: head.email for p, head, _ in derive(db, company)}
        # Jade reports to the team's head (Rio); Rio, who heads it, to the head above (Olive); Olive, at the top, to nobody.
        assert got == {"jade@getmeds.test": "rio@getmeds.test", "rio@getmeds.test": "olive@getmeds.test"}
    link(client, h, getmeds["jade"], reportsToId=getmeds["owner"]["id"])
    with app.state.sessions() as db:
        assert "jade@getmeds.test" not in {p.email for p, _, _ in derive(db, company)}
