"""The employee seed tool (2026-11-03): units, employees, placing and heads from a plan, never twice."""

from sqlalchemy import select

from modules.platform.models import Company, Identity, Unit
from modules.platform.tools.seed_employees import seed
from modules.platform.tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)


def test_a_plan_fills_the_chart_and_runs_safely_twice(app, getmeds):
    with app.state.sessions() as db:
        company = db.get(Company, db.get(Identity, getmeds["jade"]["id"]).company_id)
        domain = "getmeds.test"
        plan = {
            "units": [{"name": "HR DEPARTMENT", "kind": "department", "parent": None, "head": f"mia@{domain}"},
                      {"name": "PAYROLL", "kind": "team", "parent": "HR DEPARTMENT", "head": None},
                      {"name": "LOST", "kind": "team", "parent": "NOWHERE", "head": None}],
            "employees": [{"email": f"mia@{domain}", "fullName": "Mia  Cruz", "title": "HR Head", "unit": "HR DEPARTMENT"},
                          {"email": f"jade@{domain}", "fullName": "Jade", "title": "IT Staff", "unit": "PAYROLL"},
                          {"email": "someone@gmail.com", "fullName": "Gmail User", "title": None, "unit": "PAYROLL"}],
        }
        said, problems, added = seed(db, company, plan)
        db.commit()
        # Any email will do (the one-domain-per-company rule was removed on 2026-11-17).
        assert said["units made"] == 2 and said["employees added"] == 2 and said["employees placed"] == 3 and said["heads set"] == 1
        assert any("NOWHERE" in p for p in problems) and not any("Gmail User" in p for p in problems)
        mia = db.scalar(select(Identity).where(Identity.email == f"mia@{domain}"))
        hr = db.scalar(select(Unit).where(Unit.name == "HR DEPARTMENT"))
        assert mia.full_name == "Mia Cruz" and mia.title == "HR Head" and mia.main_unit_id == hr.id and hr.manager_id == mia.id
        again, _, _ = seed(db, company, plan)
        assert again["units made"] == 0 and again["employees added"] == 0 and again["employees placed"] == 0 and again["heads set"] == 0
        # A first password for the new, who must change it; nobody who has one is touched.
        from modules.platform.accounts import account_of
        from modules.platform.security import verify_password
        from modules.platform.tools.seed_employees import give_passwords, rename_roles

        jade = db.scalar(select(Identity).where(Identity.email == f"jade@{domain}"))
        before = jade.password_hash
        assert give_passwords(db, company, "2.4Billion", added) == 2 and jade.password_hash == before
        mia = db.scalar(select(Identity).where(Identity.email == f"mia@{domain}"))
        assert verify_password("2.4Billion", mia.password_hash) and account_of(db, mia).must_change_password
        said_roles = rename_roles(db, company, ["Nobody=Else"])
        assert "not renamed" in said_roles[0]
