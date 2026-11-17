"""Abilities (feature plan step 6): roles are copied from Bishnoi One's job roles and adjusted in plain
words, and their permissions follow. The app catalogue's on/off switches were removed on 2026-11-17."""

from modules.platform import abilities as ab
from modules.platform.tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)
from modules.platform.tests.test_identity import claims_of

CRM_PASS = {"app": "crm", "returnTo": "http://localhost:4302/auth/platform"}


def key(client):
    return client.get("/pass/key").json()["publicKey"]


def test_the_abilities_and_job_roles_are_offered_to_company_administrators(client, getmeds):
    assert client.get("/identity/access/abilities", headers=getmeds["jade"]["h"]).status_code == 403
    offered = client.get("/identity/access/abilities", headers=getmeds["owner"]["h"]).json()
    assert [g["name"] for g in offered["groups"]] == ["CRM and Sales", "Operations", "Books", "Company"]
    assert {j["key"] for j in offered["jobRoles"]} >= {"sales_rep", "team_lead", "finance_head", "company_admin"}


def test_a_role_copied_from_a_job_role_holds_what_its_abilities_need(client, getmeds):
    h = getmeds["owner"]["h"]
    r = client.post("/identity/access/roles/from-job", json={"jobRole": "team_lead", "name": "URO team lead"}, headers=h)
    assert r.status_code == 201, r.text
    role = r.json()
    assert role["jobRole"] == "team_lead" and role["scopes"]["crm"] == "team"
    # Only the company's apps (CRM and Pharmacy here): what the abilities bundle for the CRM.
    assert role["permissions"]["crm"] == ab.permissions_for(list(ab.JOB["team_lead"].abilities), {"crm"})["crm"]
    assert "quotes.approve" in role["permissions"]["crm"]
    assert {"key": "discounts.approve", "limit": 10} in role["abilities"]
    assert client.post("/identity/access/roles/from-job", json={"jobRole": "team_lead", "name": "URO team lead"}, headers=h).status_code == 422

    # Switched off in plain words: the permission goes; the limit changes.
    kept = [a for a in role["abilities"] if a["key"] != "discounts.approve"]
    kept = [{**a, "limit": 8} if a["key"] == "discounts.give" else a for a in kept]
    changed = client.put(f"/identity/access/roles/{role['id']}/abilities", json={"abilities": kept}, headers=h).json()
    assert "quotes.approve" not in changed["permissions"]["crm"]
    assert {"key": "discounts.give", "limit": 8} in changed["abilities"]
    assert changed["scopes"]["crm"] == "team"  # kept

    # Jade is given it: her pass carries the role with its abilities, for workflows to check.
    client.put(f"/identity/access/people/{getmeds['jade']['id']}/role", json={"roleId": role["id"]}, headers=h)
    p = client.post("/identity/pass", json=CRM_PASS, headers=getmeds["jade"]["h"])
    role_def = claims_of(p.json()["pass"], key(client))["roleDef"]
    assert role_def["name"] == "URO team lead" and {"key": "discounts.give", "limit": 8} in role_def["abilities"]


def test_the_company_administrator_job_role_has_everything(client, getmeds):
    r = client.post("/identity/access/roles/from-job", json={"jobRole": "company_admin", "name": "Owners"}, headers=getmeds["owner"]["h"]).json()
    assert r["isAdmin"] and r["abilities"] == []
    assert client.put(f"/identity/access/roles/{r['id']}/abilities", json={"abilities": []}, headers=getmeds["owner"]["h"]).status_code == 409


def test_there_are_no_catalogue_switches_any_more(client, getmeds):
    """Removed 2026-11-17 (owner decision): every company runs everything it is subscribed to."""
    h = getmeds["owner"]["h"]
    assert client.get("/identity/company/catalogue", headers=h).status_code == 404
    assert client.put("/identity/company/catalogue/crm", json={"on": False}, headers=h).status_code == 404
    me = client.get("/identity/me", headers=getmeds["jade"]["h"]).json()
    assert "features" not in me and "crm" in {a["key"] for a in me["apps"]}
    slug = getmeds["company"]["slug"]
    pass_claims = claims_of(client.get(f"/public/company-pass?app=crm&company={slug}").json()["pass"], key(client))
    assert "features" not in pass_claims
    assert client.post("/identity/pass", json=CRM_PASS, headers=getmeds["jade"]["h"]).status_code == 200
