"""The employee seed tool (2026-11-03): units, employees, placing and heads from a plan, never twice."""

from sqlalchemy import select

from app.models import Company, Identity, Unit
from app.tools.seed_employees import seed
from tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)


def test_a_plan_fills_the_chart_and_runs_safely_twice(app, getmeds):
    with app.state.sessions() as db:
        company = db.get(Company, db.get(Identity, getmeds["jade"]["id"]).company_id)
        domain = "getmeds.test"
        company.email_domain = domain  # as live: Getmeds signs in with @getmeds.ph
        plan = {
            "units": [{"name": "HR DEPARTMENT", "kind": "department", "parent": None, "head": f"mia@{domain}"},
                      {"name": "PAYROLL", "kind": "team", "parent": "HR DEPARTMENT", "head": None},
                      {"name": "LOST", "kind": "team", "parent": "NOWHERE", "head": None}],
            "employees": [{"email": f"mia@{domain}", "fullName": "Mia  Cruz", "title": "HR Head", "unit": "HR DEPARTMENT"},
                          {"email": f"jade@{domain}", "fullName": "Jade", "title": "IT Staff", "unit": "PAYROLL"},
                          {"email": "someone@gmail.com", "fullName": "Off Domain", "title": None, "unit": "PAYROLL"}],
        }
        said, problems = seed(db, company, plan)
        db.commit()
        assert said["units made"] == 2 and said["employees added"] == 1 and said["employees placed"] == 2 and said["heads set"] == 1
        assert any("NOWHERE" in p for p in problems) and any("Off Domain" in p for p in problems)
        mia = db.scalar(select(Identity).where(Identity.email == f"mia@{domain}"))
        hr = db.scalar(select(Unit).where(Unit.name == "HR DEPARTMENT"))
        assert mia.full_name == "Mia Cruz" and mia.title == "HR Head" and mia.main_unit_id == hr.id and hr.manager_id == mia.id
        again, _ = seed(db, company, plan)
        assert again["units made"] == 0 and again["employees added"] == 0 and again["employees placed"] == 0 and again["heads set"] == 0
