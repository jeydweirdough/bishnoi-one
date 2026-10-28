"""The company console and operators (feature plan step 5): a company's administrators keep their
company here; operators are a switch on an account, not a separate staff login."""

from tests.conftest import PASSWORD
from tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)


def test_only_a_company_administrator_opens_the_company_console(client, getmeds):
    for path in ("", "/apps", "/services", "/activity", "/security"):
        assert client.get(f"/identity/company{path}", headers=getmeds["jade"]["h"]).status_code == 403, path
        assert client.get(f"/identity/company{path}", headers=getmeds["owner"]["h"]).status_code == 200, path


def test_the_company_profile(client, getmeds):
    h = getmeds["owner"]["h"]
    r = client.patch("/identity/company", json={"name": "GetMeds Philippines", "contactEmail": "Admin@GetMeds.test", "timezone": "Asia/Manila"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["company"]["name"] == "GetMeds Philippines" and r.json()["company"]["contactEmail"] == "admin@getmeds.test"
    assert client.patch("/identity/company", json={"timezone": "Mars/Olympus"}, headers=h).status_code == 422
    log = client.get("/identity/company/activity", headers=h).json()["entries"]
    assert log[0]["action"] == "company.updated" and log[0]["fields"] == ["contact_email", "name"]


def test_apps_and_integrations(client, getmeds):
    h = getmeds["owner"]["h"]
    apps = {a["key"]: a for a in client.get("/identity/company/apps", headers=h).json()["apps"]}
    assert set(apps) == {"crm", "pharmacy"} and apps["crm"]["people"] == 2  # Jade and Rio
    services = {s["key"]: s for s in client.get("/identity/company/services", headers=h).json()["services"]}
    assert "smtp" in services
    smtp = services["smtp"]
    values = {d["key"]: "x" for d in smtp["details"] if d["required"] and not d["options"]}
    values |= {d["key"]: d["options"][0]["value"] for d in smtp["details"] if d["required"] and d["options"]}
    saved = client.put("/identity/company/services/smtp", json={"values": values, "enabled": True}, headers=h)
    assert saved.status_code == 200, saved.text
    assert saved.json()["enabled"] and all(not d.get("value") or not d["secret"] for d in saved.json()["details"])  # secrets never come back


def test_security_lists_sign_ins_and_ends_them(client, getmeds):
    h = getmeds["owner"]["h"]
    s = client.get("/identity/company/security", headers=h).json()
    jade = next(p for p in s["people"] if p["email"] == "jade@getmeds.test")
    assert jade["hasPassword"] and jade["openSignIns"] == 1
    assert client.post(f"/identity/company/security/people/{jade['id']}/sign-out", headers=h).json() == {"ended": 1}
    assert client.get("/identity/me", headers=getmeds["jade"]["h"]).status_code == 401


def test_operators_are_a_switch_on_the_account(client, ana, getmeds):
    ops = client.get("/platform/operators", headers=ana).json()
    assert [o["email"] for o in ops["operators"]] == ["ana@example.com"]
    found = client.get("/platform/operators", params={"q": "jade"}, headers=ana).json()["found"]
    assert [f["email"] for f in found] == ["jade@getmeds.test"]
    # The last operator can't be switched off, nor can you switch yourself off.
    assert client.put(f"/platform/operators/{ops['operators'][0]['id']}", json={"isOperator": False}, headers=ana).status_code == 409
    r = client.put(f"/platform/operators/{found[0]['id']}", json={"isOperator": True}, headers=ana)
    assert r.status_code == 200 and r.json()["operator"]["isOperator"]
    # Jade now sees the Operations area with her one sign-in.
    jade = getmeds["jade"]["h"]
    assert client.get("/identity/me", headers=jade).json()["staff"] == "admin"
    assert client.get("/platform/companies", headers=jade).status_code == 200
    # Switched off again: the Operations area closes.
    client.put(f"/platform/operators/{found[0]['id']}", json={"isOperator": False}, headers=ana)
    assert client.get("/identity/me", headers=jade).json()["staff"] is None
    assert client.get("/platform/companies", headers=jade).status_code == 401


def test_the_staff_sign_in_is_closed_on_a_server(app, client):
    app.state.settings.environment = "production"
    try:
        r = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
        assert r.status_code == 403 and "Bishnoi One account" in r.json()["detail"]
    finally:
        app.state.settings.environment = "development"
