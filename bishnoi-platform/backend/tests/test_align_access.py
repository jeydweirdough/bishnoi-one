"""The align-access tool (2026-11-04): who gets the CRM, and with which chart role."""

from sqlalchemy import select

from app import access_roles
from app.models import AccessRole, Company, Identity
from app.tools.align_access import level_of, plan
from tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)
from tests.test_unit_heads import unit


def test_only_unplaced_crm_holders_in_the_department_are_chosen_and_titles_pick_the_role(app, client, getmeds):
    h = getmeds["owner"]["h"]
    dept = unit(client, h, "department", "SALES DEPARTMENT")
    team = unit(client, h, "team", "B2C", parent=dept["id"])
    other = unit(client, h, "department", "HR DEPARTMENT")
    mia = client.post("/identity/access/people", json={"fullName": "Mia Cruz", "email": "mia@getmeds.test"}, headers=h).json()["person"]
    lead = client.post("/identity/access/people", json={"fullName": "Team Person", "email": "lead@getmeds.test", "title": "Sales Team Lead"}, headers=h).json()["person"]
    hr = client.post("/identity/access/people", json={"fullName": "Hr Person", "email": "hr@getmeds.test"}, headers=h).json()["person"]
    for who, where in ((mia, team), (lead, team), (hr, other), (getmeds["jade"], team)):
        client.put(f"/identity/organisation/people/{who['id']}", json={"mainUnitId": where["id"]}, headers=h)
    with app.state.sessions() as db:
        company = db.get(Company, db.get(Identity, mia["id"]).company_id)
        roles = {n: AccessRole(company_id=company.id, name=n) for n in ("Mentor", "Coach", "Coachee")}
        db.add_all(roles.values())
        db.flush()
        crm = next(m for m in access_roles.modules_of(db, company.id) if m.key == "crm")
        rows = plan(db, company, "sales department", crm, roles)
        got = {r["person"].email: r["level"] for r in rows}
        # Jade already holds the CRM and HR is another department: only Mia and the team lead.
        assert got == {"mia@getmeds.test": "Coachee", "lead@getmeds.test": "Coach"}
        named = db.scalar(select(Identity).where(Identity.id == mia["id"]))
        named.full_name = "Javed Shaikh"
        assert level_of(named) == "Mentor"
