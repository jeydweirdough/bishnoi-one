"""One email, one account; one email domain per company (decided 2026-10-29, app/email_rules.py)."""

import json

from sqlalchemy import select

from app.models import Account, Company, Identity, User
from app.tools import email_domains
from tests.conftest import PASSWORD, make_company
from tests.test_company_access import getmeds, modules, person  # noqa: F401 (fixtures)


def domain(client, h, value):
    return client.patch("/identity/company", json={"emailDomain": value}, headers=h)


def test_the_company_sets_one_domain_of_its_own(client, ana, getmeds):
    h = getmeds["owner"]["h"]
    assert domain(client, h, "gmail.com").status_code == 422  # a public mailbox
    assert domain(client, h, "not a domain").status_code == 422
    r = domain(client, h, "@GetMeds.test")
    assert r.status_code == 200, r.text
    assert r.json()["company"]["emailDomain"] == "getmeds.test" and r.json()["offDomain"] == []
    # Another company can't have it.
    other = make_company(client, ana, name="2MG")
    clash = client.patch(f"/platform/companies/{other['id']}", json={"emailDomain": "getmeds.test"}, headers=ana)
    assert clash.status_code == 422 and "another company" in clash.text


def test_people_are_added_and_changed_only_at_the_domain_and_never_twice(client, ana, getmeds):
    h = getmeds["owner"]["h"]
    domain(client, h, "getmeds.test")
    wrong = client.post("/identity/access/people", json={"fullName": "Gina Gmail", "email": "gina@gmail.com"}, headers=h)
    assert wrong.status_code == 422 and "@getmeds.test" in wrong.text
    assert client.post("/identity/access/people", json={"fullName": "Gina Cruz", "email": "gina@getmeds.test"}, headers=h).status_code == 201
    # An operator's email isn't available to any company, and a person's isn't to another company.
    other = make_company(client, ana, name="2MG")
    client.patch(f"/platform/companies/{other['id']}", json={"emailDomain": "example.com"}, headers=ana)
    taken = client.post("/platform/users", json={"companyId": other["id"], "fullName": "Ana", "email": "ana@example.com"}, headers=ana)
    assert taken.status_code == 422 and "isn't available" in taken.text
    client.patch(f"/platform/companies/{other['id']}", json={"emailDomain": ""}, headers=ana)
    elsewhere = client.post("/platform/users", json={"companyId": other["id"], "fullName": "Gina", "email": "gina@getmeds.test"}, headers=ana)
    assert elsewhere.status_code == 422 and "isn't available" in elsewhere.text


def gmail_jade(app, getmeds) -> str:
    """Jade signs in as jade@gmail.com, from before the company set its domain."""
    with app.state.sessions() as db:
        from app import email_rules
        email_rules.change_email(db, db.get(Identity, getmeds["jade"]["id"]), "jade@gmail.com")
        db.commit()
    return getmeds["jade"]["id"]


def test_an_administrator_changes_someones_email_and_their_password_stays(app, client, getmeds):
    h = getmeds["owner"]["h"]
    jade = gmail_jade(app, getmeds)
    assert client.get("/identity/me", headers=getmeds["jade"]["h"]).status_code == 200
    domain(client, h, "getmeds.test")  # Jade's isn't at it: she's stopped, and listed to change
    assert client.get("/identity/me", headers=getmeds["jade"]["h"]).status_code == 401
    assert [p["email"] for p in client.get("/identity/company", headers=h).json()["offDomain"]] == ["jade@gmail.com"]
    assert client.patch(f"/identity/access/people/{jade}", json={"email": "jade@other.test"}, headers=h).status_code == 422
    assert client.patch(f"/identity/access/people/{jade}", json={"email": "rio@getmeds.test"}, headers=h).status_code == 422  # Rio's
    r = client.patch(f"/identity/access/people/{jade}", json={"email": "Jade.M@getmeds.test"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["person"]["email"] == "jade.m@getmeds.test"
    with app.state.sessions() as db:
        assert db.scalar(select(Account).where(Account.email == "jade@gmail.com")) is None
        assert db.scalar(select(Account).where(Account.email == "jade.m@getmeds.test")) is not None
    assert client.get("/identity/company", headers=h).json()["offDomain"] == []


def test_sign_in_is_stopped_until_the_email_is_at_the_domain(app, client, getmeds):
    h = getmeds["owner"]["h"]
    jade = gmail_jade(app, getmeds)
    client.post(f"/identity/access/people/{jade}/password", json={"password": "a new password 1"}, headers=h)
    domain(client, h, "getmeds.test")
    r = client.post("/identity/login", json={"email": "jade@gmail.com", "password": "a new password 1"})
    assert r.status_code == 403 and "@getmeds.test" in r.json()["detail"]
    client.patch(f"/identity/access/people/{jade}", json={"email": "jade@getmeds.test"}, headers=h)
    assert client.post("/identity/login", json={"email": "jade@getmeds.test", "password": "a new password 1"}).status_code == 200


def test_an_operator_has_an_email_of_their_own(client, ana, getmeds):
    h = getmeds["owner"]["h"]
    # A company's person isn't made an operator: the operator signs in with another email.
    found = client.get("/platform/people?q=jade", headers=ana).json()["people"]
    assert found[0]["memberships"][0]["company"] == "GetMeds" and not found[0]["isOperator"]
    assert client.put(f"/platform/operators/{found[0]['id']}", json={"isOperator": True}, headers=ana).status_code == 409
    assert client.post("/platform/operators", json={"email": "jade@getmeds.test", "fullName": "Jade", "password": "long enough 1"}, headers=ana).status_code == 422
    r = client.post("/platform/operators", json={"email": "jade@bishnoione.test", "fullName": "Jade Madigal", "password": "long enough 1"}, headers=ana)
    assert r.status_code == 201, r.text
    signed = client.post("/identity/login", json={"email": "jade@bishnoione.test", "password": "long enough 1"})
    assert signed.status_code == 200, signed.text
    me = client.get("/identity/me", headers={"Authorization": f"Bearer {signed.json()['accessToken']}"}).json()
    assert me["staff"] == "admin" and me["isCompanyAdmin"]
    # Not one of GetMeds' people, and a company can't take the email.
    assert all(p["email"] != "jade@bishnoione.test" for p in client.get("/identity/access", headers=h).json()["people"])
    assert client.post("/identity/access/people", json={"fullName": "J", "email": "jade@bishnoione.test"}, headers=h).status_code == 422


def test_the_tool_separates_operators_moves_people_and_changes_emails(app, client, ana, tmp_path):
    a = make_company(client, ana, name="Getmeds", slug="getmeds")
    with app.state.sessions() as db:
        for email, name in (("naresh@getmeds.ph", "Naresh"), ("naresh@getmeds.ph / naresh@2mginc.com", "Naresh Kumar"),
                            ("dra@2mginc.com", "Alikka"), ("someone@gmail.com", "Some One")):
            db.add(Identity(company_id=a["id"], full_name=name, email=email, is_company_admin=email == "naresh@getmeds.ph"))
        db.add(User(email="naresh@getmeds.ph", full_name="Naresh", password_hash="x", role="admin"))
        db.commit()
    assert client.post("/identity/login", json={"email": "ana@example.com", "password": PASSWORD}).status_code == 200  # Ana's let-in membership
    plan = {"domains": {"getmeds": "getmeds.ph"},
            "duplicates": [{"company": "getmeds", "email": "naresh@getmeds.ph / naresh@2mginc.com", "keep": "naresh@getmeds.ph"}],
            "operators": {"naresh@getmeds.ph": "naresh@bishnoione.ai", "ana@example.com": "ana@bishnoione.ai"},
            "newCompanies": [{"name": "2MG", "slug": "2mg", "domain": "2mginc.com", "moveFrom": "getmeds"}],
            "emails": {"someone@gmail.com": "some.one@getmeds.ph"}}
    with app.state.sessions() as db:
        email_domains.run(db, plan)
        assert email_domains.report(db) == 0
        db.commit()
        email_domains.run(db, plan)  # safe to run twice
        db.commit()
    with app.state.sessions() as db:
        accounts = {x.email: x for x in db.scalars(select(Account))}
        assert accounts["naresh@bishnoione.ai"].is_operator and not accounts["naresh@getmeds.ph"].is_operator
        assert accounts["ana@bishnoione.ai"].is_operator and "ana@example.com" not in accounts
        ana_in = db.scalar(select(Identity).where(Identity.company_id == a["id"], Identity.via_operator))
        assert ana_in.email == "ana@bishnoione.ai" and ana_in.account_id == accounts["ana@bishnoione.ai"].id
        two = db.scalar(select(Company).where(Company.slug == "2mg"))
        alikka = db.scalars(select(Identity).where(Identity.email == "dra@2mginc.com")).all()
        assert {(m.company_id == two.id, m.status) for m in alikka} == {(True, "active"), (False, "suspended")}
        assert len({m.account_id for m in alikka}) == 1  # the same account, with its password
        assert db.scalar(select(Identity).where(Identity.email == "some.one@getmeds.ph")).full_name == "Some One"
        broken = db.scalar(select(Identity).where(Identity.full_name == "Naresh Kumar"))
        assert broken.status == "suspended"
    staff = client.post("/identity/login", json={"email": "ana@bishnoione.ai", "password": PASSWORD})
    assert staff.status_code == 200, staff.text


def test_the_tool_reads_a_plan_file(app, tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"emails": {"nobody@gmail.com": ""}}), encoding="utf-8")
    with app.state.sessions() as db:
        email_domains.run(db, json.loads(path.read_text(encoding="utf-8")))  # "" = not given yet: skipped
