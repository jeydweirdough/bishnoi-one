"""One account per person, and the org chart (feature plan step 4, agreed 2026-10-28)."""

import importlib.util
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select, text

from app.config import API_DIR
from app.models import Account, Company, Identity, MembershipUnit, Unit, User
from app.security import hash_password
from app.tools import org_chart
from tests.conftest import PASSWORD, make_company


def migration():
    spec = importlib.util.spec_from_file_location("m0013", API_DIR / "migrations" / "versions" / "0013_accounts_and_org_chart.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_migration_makes_one_account_per_person_keeping_the_newer_password(app, client, ana):
    a, b = make_company(client, ana), make_company(client, ana, name="Northwind")
    old, new = datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 20, tzinfo=UTC)
    with app.state.sessions() as db:
        db.add(Identity(company_id=a["id"], full_name="Rita Cruz", email="rita@getmeds.ph", password_hash=hash_password("old one"), password_changed_at=old))
        db.add(Identity(company_id=b["id"], full_name="Rita Cruz", email="RITA@getmeds.ph", password_hash=hash_password("new one"), password_changed_at=new))
        db.commit()
    engine = app.state.sessions.kw["bind"]
    with engine.begin() as c:  # as the live database was before the migration: no accounts
        c.execute(text("update nbpl_identities set account_id = null"))
        c.execute(text("delete from nbpl_accounts"))
        c.execute(text("update nbpl_users set password_changed_at = :t where email = 'ana@example.com'"), {"t": old})
        migration().bring_in(c)
        migration().bring_in(c)  # safe to run twice
    with app.state.sessions() as db:
        accounts = {x.email: x for x in db.scalars(select(Account))}
        assert set(accounts) == {"rita@getmeds.ph", "ana@example.com", "ben@example.com"}
        rita = accounts["rita@getmeds.ph"]
        assert {m.account_id for m in db.scalars(select(Identity).where(Identity.email.ilike("rita@getmeds.ph")))} == {rita.id}
        assert accounts["ana@example.com"].is_operator and not accounts["ben@example.com"].is_operator
    r = client.post("/identity/login", json={"email": "rita@getmeds.ph", "password": "new one"})
    assert r.status_code == 200, r.text
    assert client.post("/identity/login", json={"email": "rita@getmeds.ph", "password": "old one"}).status_code == 401


def test_a_suspended_account_is_stopped_everywhere(app, client, ana):
    a = make_company(client, ana)
    with app.state.sessions() as db:
        db.add(Identity(company_id=a["id"], full_name="Rita Cruz", email="rita@getmeds.ph", password_hash=hash_password(PASSWORD)))
        db.commit()
    signed = client.post("/identity/login", json={"email": "rita@getmeds.ph", "password": PASSWORD})
    h = {"Authorization": f"Bearer {signed.json()['accessToken']}"}
    assert client.get("/identity/me", headers=h).status_code == 200
    with app.state.sessions() as db:
        db.scalar(select(Account).where(Account.email == "rita@getmeds.ph")).status = "suspended"
        db.commit()
    assert client.get("/identity/me", headers=h).status_code == 401
    r = client.post("/identity/login", json={"email": "rita@getmeds.ph", "password": PASSWORD})
    assert r.status_code == 403 and "suspended" in r.json()["detail"]


def test_an_operator_has_a_membership_at_every_company_made_for_them(app, client, ana):
    """One email, one person (2026-10-28): the membership made for an operator only lets them in; they
    administer the company by the switch on their account, not by being ticked as its administrator."""
    make_company(client, ana)
    r = client.post("/identity/login", json={"email": "ana@example.com", "password": PASSWORD})
    assert r.status_code == 200, r.text
    with app.state.sessions() as db:
        mine = db.scalars(select(Identity).where(Identity.email == "ana@example.com")).all()
        assert len(mine) == 1 and mine[0].via_operator and not mine[0].is_company_admin
    h = {"Authorization": f"Bearer {r.json()['accessToken']}"}
    assert client.get("/identity/me", headers=h).json()["isCompanyAdmin"] is True  # by the operator switch
    access = client.get("/identity/access", headers=h)
    assert access.status_code == 200
    assert all(p["email"] != "ana@example.com" for p in access.json()["people"])  # not one of the company's people


def test_an_operator_who_works_at_a_company_keeps_what_the_company_set(app, client, ana):
    """An operator the company made a plain member stays one there: their sign-in changes nothing of the company's."""
    a = make_company(client, ana)
    with app.state.sessions() as db:
        db.add(Identity(company_id=a["id"], full_name="Ana Reyes", email="ana@example.com", title="Medical rep"))
        db.commit()
    for _ in range(2):  # signing in again changes nothing either
        assert client.post("/identity/login", json={"email": "ana@example.com", "password": PASSWORD}).status_code == 200
    with app.state.sessions() as db:
        rows = db.scalars(select(Identity).where(Identity.email == "ana@example.com")).all()
        assert len(rows) == 1  # one membership at the company: the one it made
        assert not rows[0].is_company_admin and not rows[0].via_operator and rows[0].title == "Medical rep"
        accounts = db.scalars(select(Account).where(Account.email == "ana@example.com")).all()
        assert len(accounts) == 1 and accounts[0].is_operator


def test_the_crm_teams_become_the_org_chart_with_their_ids(app, client, ana):
    a = make_company(client, ana)
    with app.state.sessions() as db:
        for email in ("lead@getmeds.ph", "rep@getmeds.ph", "new@getmeds.ph"):
            db.add(Identity(company_id=a["id"], full_name=email, email=email))
        db.commit()
    hos, field, train = "11111111-0000-4000-8000-000000000001", "11111111-0000-4000-8000-000000000002", "11111111-0000-4000-8000-000000000003"
    teams = [
        SimpleNamespace(id=field, name="Field NCR 1", parent_id=hos, headquarters=["Commonwealth"], is_active=True, manager="lead@getmeds.ph"),
        SimpleNamespace(id=hos, name="HOS", parent_id=None, headquarters='["Cebu", "Davao"]', is_active=True, manager=None),
        SimpleNamespace(id=train, name="Training", parent_id=None, headquarters=[], is_active=True, manager=None),
    ]
    people = [SimpleNamespace(email="rep@getmeds.ph", team_id=field, is_active=True), SimpleNamespace(email="lead@getmeds.ph", team_id=hos, is_active=True)]
    others = [SimpleNamespace(email="rep@getmeds.ph", team_id=train)]
    with app.state.sessions() as db:
        company = db.get(Company, a["id"])
        said = org_chart.bring_in(db, company, teams, people, others)
        db.commit()
        again = org_chart.bring_in(db, company, teams, people, others)  # safe to run twice
        db.commit()
        units = {u.id: u for u in db.scalars(select(Unit))}
        assert units[hos].kind == "division" and units[field].kind == "team" and units[field].parent_id == hos
        assert units[hos].areas == ["Cebu", "Davao"]
        lead = db.scalar(select(Identity).where(Identity.email == "lead@getmeds.ph"))
        rep = db.scalar(select(Identity).where(Identity.email == "rep@getmeds.ph"))
        assert units[field].manager_id == lead.id
        assert rep.main_unit_id == field and db.get(MembershipUnit, (rep.id, train)) is not None
        assert said["people placed"] == 2 and said["not placed"] == 1  # new@ isn't in the CRM
        assert again["units already there"] == 3 and again["people placed"] == 0


def test_a_new_staff_member_joins_the_account_with_its_password(app, client, ana):
    """While staff records last (step 5 retires them), a staff record with an existing account's email
    doesn't replace its password, and a Platform Admin's account is an operator's."""
    a = make_company(client, ana)
    with app.state.sessions() as db:
        db.add(Identity(company_id=a["id"], full_name="Jade", email="jade@getmeds.ph", password_hash=hash_password("account one")))
        db.commit()
        db.add(User(email="jade@getmeds.ph", full_name="Jade", password_hash=hash_password("staff one"), role="admin",
                    password_changed_at=datetime.now(UTC) + timedelta(seconds=1)))
        db.commit()
        account = db.scalar(select(Account).where(Account.email == "jade@getmeds.ph"))
        assert account.is_operator
    assert client.post("/identity/login", json={"email": "jade@getmeds.ph", "password": "account one"}).status_code == 200
