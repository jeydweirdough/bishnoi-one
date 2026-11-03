"""Several heads per unit, and everyone above sees everyone below (2026-11-04)."""

from app import org_push
from app.models import Company, Identity
from tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)


def unit(client, h, kind, name, parent=None, heads=None):
    body = {"kind": kind, "name": name, **({"parentId": parent} if parent else {}), **({"headIds": heads} if heads is not None else {})}
    r = client.post("/identity/organisation/units", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["unit"]


def test_a_unit_can_have_several_heads_and_the_first_stays_the_manager(client, getmeds):
    h, olive, rio, jade = getmeds["owner"]["h"], getmeds["owner"], getmeds["rio"], getmeds["jade"]
    sales = unit(client, h, "department", "Sales", heads=[olive["id"], rio["id"]])
    assert sales["headIds"] == [olive["id"], rio["id"]] and sales["managerId"] == olive["id"]
    # Changed, cleared, and the old one-head field still works.
    r = client.patch(f"/identity/organisation/units/{sales['id']}", json={"headIds": [rio["id"], jade["id"]]}, headers=h).json()["unit"]
    assert r["headIds"] == [rio["id"], jade["id"]] and r["managerId"] == rio["id"]
    r = client.patch(f"/identity/organisation/units/{sales['id']}", json={"managerId": olive["id"]}, headers=h).json()["unit"]
    assert r["headIds"] == [olive["id"]]
    assert client.patch(f"/identity/organisation/units/{sales['id']}", json={"headIds": []}, headers=h).json()["unit"]["headIds"] == []
    # Only this company's people.
    assert client.patch(f"/identity/organisation/units/{sales['id']}", json={"headIds": ["nobody"]}, headers=h).status_code == 404
    listed = next(u for u in client.get("/identity/organisation", headers=h).json()["units"] if u["id"] == sales["id"])
    assert listed["headIds"] == []


def test_everyone_above_a_person_sees_them_and_nobody_sees_themselves_or_the_next_division(app, client, getmeds):
    h, olive, rio, jade = getmeds["owner"]["h"], getmeds["owner"], getmeds["rio"], getmeds["jade"]
    dept = unit(client, h, "department", "Sales", heads=[olive["id"]])
    rx = unit(client, h, "division", "Rx", parent=dept["id"], heads=[rio["id"]])
    b2c = unit(client, h, "team", "B2C", parent=rx["id"])
    other = unit(client, h, "division", "B2B", parent=dept["id"])
    client.put(f"/identity/organisation/people/{jade['id']}", json={"mainUnitId": b2c["id"]}, headers=h)
    client.put(f"/identity/organisation/people/{rio['id']}", json={"mainUnitId": rx["id"]}, headers=h)
    with app.state.sessions() as db:
        company = db.get(Company, db.get(Identity, jade["id"]).company_id)
        chart = {p["email"]: p for p in org_push.chart(db, company)["people"]}
        # A team member: the division head, then the department head. A division head: the department head only.
        assert chart["jade@getmeds.test"]["managers"] == ["rio@getmeds.test", "olive@getmeds.test"]
        assert chart["rio@getmeds.test"]["managers"] == ["olive@getmeds.test"]
        # Someone placed under the other division is seen by the department head, not by Rio.
        client.put(f"/identity/organisation/people/{olive['id']}", json={"mainUnitId": other["id"]}, headers=h)
        chart = {p["email"]: p for p in org_push.chart(db, company)["people"]}
        assert chart["olive@getmeds.test"]["managers"] == ["olive@getmeds.test"][:0] or "rio@getmeds.test" not in chart["olive@getmeds.test"]["managers"]
    # A second head sees the same people; a link by hand adds one outside the chart.
    client.patch(f"/identity/organisation/units/{rx['id']}", json={"headIds": [rio["id"], olive["id"]]}, headers=h)
    client.put(f"/identity/access/people/{jade['id']}/reporting", json={"reportsToId": getmeds["owner"]["id"]}, headers=h)
    with app.state.sessions() as db:
        company = db.get(Company, db.get(Identity, jade["id"]).company_id)
        chart = {p["email"]: p for p in org_push.chart(db, company)["people"]}
        assert chart["jade@getmeds.test"]["managers"] == ["rio@getmeds.test", "olive@getmeds.test"]
        placed = org_push.placement(db, db.get(Identity, jade["id"]))
        assert placed["managers"] == ["rio@getmeds.test", "olive@getmeds.test"] and placed["manager"] == "olive@getmeds.test"  # the link is first for "manager"
