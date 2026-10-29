"""The app catalogue and abilities (feature plan step 6): a company turns apps and features on or off;
roles are copied from Bishnoi One's job roles and adjusted in plain words, and their permissions follow."""

from app import abilities as ab
from tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)
from tests.test_identity import claims_of

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


def test_the_catalogue_turns_apps_and_features_on_and_off(client, getmeds):
    h = getmeds["owner"]["h"]
    apps = {a["key"]: a for a in client.get("/identity/company/catalogue", headers=h).json()["apps"]}
    assert apps["crm"]["on"] and apps["field_sales"]["on"] and not apps["inventory"]["on"]
    assert not apps["warehouse"]["later"] and not apps["warehouse"]["on"]  # quality checks built (step 14a); runs in Inventory, which this company hasn't got
    assert not apps["sales"]["later"] and not apps["sales"]["on"]  # built (step 11); runs in Inventory, which this company hasn't got
    # A feature of an app the company hasn't got, and a feature not built yet, are refused.
    assert client.put("/identity/company/catalogue/inventory.batches", json={"on": True}, headers=h).status_code == 409
    assert client.put("/identity/company/catalogue/field_sales.samples", json={"on": True}, headers=h).status_code == 409
    # Purchasing on: the company gets the Inventory service it runs in.
    after = {a["key"]: a for a in client.put("/identity/company/catalogue/purchasing", json={"on": True}, headers=h).json()["apps"]}
    assert after["purchasing"]["on"] and after["inventory"]["on"]
    # A feature off: everyone's /identity/me says so, and the company pass carries it.
    client.put("/identity/company/catalogue/crm.lead_inbox", json={"on": False}, headers=h)
    me = client.get("/identity/me", headers=getmeds["jade"]["h"]).json()
    assert me["features"]["crm.lead_inbox"] is False and me["features"]["crm.deals"] is True
    slug = getmeds["company"]["slug"]
    pass_claims = claims_of(client.get(f"/public/company-pass?app=crm&company={slug}").json()["pass"], key(client))
    assert pass_claims["features"]["crm.lead_inbox"] is False and "inventory.batches" not in pass_claims["features"]
    log = client.get("/identity/company/activity", headers=h).json()["entries"]
    assert log[0]["action"] == "catalogue.switched_off"


def test_a_service_whose_apps_are_all_off_isnt_opened(client, getmeds):
    h = getmeds["owner"]["h"]
    for app in ("crm", "field_sales"):
        client.put(f"/identity/company/catalogue/{app}", json={"on": False}, headers=h)
    jade = getmeds["jade"]["h"]
    assert "crm" not in {a["key"] for a in client.get("/identity/me", headers=jade).json()["apps"]}
    r = client.post("/identity/pass", json=CRM_PASS, headers=jade)
    assert r.status_code == 403 and "switched" in r.json()["detail"]
    client.put("/identity/company/catalogue/field_sales", json={"on": True}, headers=h)
    assert client.post("/identity/pass", json=CRM_PASS, headers=jade).status_code == 200
