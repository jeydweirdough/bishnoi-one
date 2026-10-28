"""The company's org chart, kept by its administrators on the Platform (feature plan step 4):
units, branches, where people sit; the applications are sent it, and each pass carries the person's placing."""

import pytest

from app import org_push
from tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)
from tests.test_identity import claims_of


@pytest.fixture
def pushed(monkeypatch):
    calls = []
    monkeypatch.setattr(org_push, "push", lambda sessions, settings, company_id: (calls.append(company_id), org_push._send(sessions, settings, company_id)))
    return calls


def test_only_a_company_administrator_keeps_the_org_chart(client, getmeds):
    assert client.get("/identity/organisation", headers=getmeds["jade"]["h"]).status_code == 403
    assert client.get("/identity/organisation", headers=getmeds["owner"]["h"]).status_code == 200


def test_units_branches_and_where_people_sit(client, getmeds, modules, pushed):
    h = getmeds["owner"]["h"]
    hos = client.post("/identity/organisation/units", json={"kind": "division", "name": "HOS", "areas": ["Cebu", " Cebu ", "Davao"]}, headers=h)
    assert hos.status_code == 201, hos.text
    hos = hos.json()["unit"]
    assert hos["areas"] == ["Cebu", "Davao"]
    field = client.post("/identity/organisation/units", json={"kind": "team", "name": "Field NCR 1", "parentId": hos["id"],
                                                             "managerId": getmeds["rio"]["id"]}, headers=h).json()["unit"]
    # The same name under the same unit, and a unit under itself, are refused.
    assert client.post("/identity/organisation/units", json={"kind": "team", "name": "field ncr 1", "parentId": hos["id"]}, headers=h).status_code == 422
    assert client.patch(f"/identity/organisation/units/{hos['id']}", json={"parentId": field["id"]}, headers=h).status_code == 422
    # A unit with units under it can't be switched off; Training becomes a department.
    assert client.patch(f"/identity/organisation/units/{hos['id']}", json={"isActive": False}, headers=h).status_code == 409
    train = client.post("/identity/organisation/units", json={"kind": "division", "name": "Training"}, headers=h).json()["unit"]
    assert client.patch(f"/identity/organisation/units/{train['id']}", json={"kind": "department"}, headers=h).json()["unit"]["kind"] == "department"

    cebu = client.post("/identity/organisation/branches", json={"name": "Cebu", "address": "Cebu City"}, headers=h)
    assert cebu.status_code == 201, cebu.text
    cebu = cebu.json()["branch"]
    assert client.post("/identity/organisation/branches", json={"name": "cebu"}, headers=h).status_code == 422

    jade = getmeds["jade"]["id"]
    r = client.put(f"/identity/organisation/people/{jade}", json={"mainUnitId": field["id"], "otherUnitIds": [train["id"], field["id"]], "branchId": cebu["id"]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["otherUnitIds"] == [train["id"]]

    chart = client.get("/identity/organisation", headers=h).json()
    me = next(p for p in chart["people"] if p["id"] == jade)
    assert me["mainUnitId"] == field["id"] and me["branchId"] == cebu["id"]
    assert next(u for u in chart["units"] if u["id"] == field["id"])["people"] == 1
    assert chart["notPlaced"] == 2  # Olive and Rio

    # The applications were sent the chart, signed.
    notes = [body for url, body in modules if url.endswith("/platform/events")]
    assert notes and pushed
    key = client.get("/pass/key").json()["publicKey"]
    claims = claims_of(notes[-1]["pass"], key)
    assert claims["kind"] == "event" and claims["aud"] == "crm" and claims["event"]["kind"] == "organisation.changed"
    chart = claims["event"]["data"]
    assert {"email": "jade@getmeds.test", "unit": field["id"], "otherUnits": [train["id"]]} in chart["people"]
    assert next(u for u in chart["units"] if u["id"] == field["id"])["manager"] == "rio@getmeds.test"

    # Jade's pass says where she sits, and who her manager is.
    p = client.post("/identity/pass", json={"app": "crm", "returnTo": "http://localhost:4302/auth/platform"}, headers=getmeds["jade"]["h"])
    assert p.status_code == 200, p.text
    org = claims_of(p.json()["pass"], key)["org"]
    assert org["unit"]["id"] == field["id"] and org["units"] == [hos["id"], field["id"]]
    assert org["branch"]["name"] == "Cebu" and org["manager"] == "rio@getmeds.test"


def test_placement_names_the_manager_above_a_unit_head(app, client, getmeds):
    h = getmeds["owner"]["h"]
    top = client.post("/identity/organisation/units", json={"kind": "division", "name": "B2B", "managerId": getmeds["owner"]["id"]}, headers=h).json()["unit"]
    team = client.post("/identity/organisation/units", json={"kind": "team", "name": "NBD", "parentId": top["id"], "managerId": getmeds["rio"]["id"]}, headers=h).json()["unit"]
    client.put(f"/identity/organisation/people/{getmeds['rio']['id']}", json={"mainUnitId": team["id"]}, headers=h)
    from app.models import Identity

    with app.state.sessions() as db:
        rio = db.get(Identity, getmeds["rio"]["id"])
        assert org_push.placement(db, rio)["manager"] == "olive@getmeds.test"
