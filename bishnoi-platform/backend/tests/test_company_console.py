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
    # GetMeds' Jade isn't made an operator: an operator has an email of their own (2026-10-29).
    assert client.put(f"/platform/operators/{found[0]['id']}", json={"isOperator": True}, headers=ana).status_code == 409
    r = client.post("/platform/operators", json={"email": "jade@bishnoione.test", "fullName": "Jade Madigal", "password": "long enough 1"}, headers=ana)
    assert r.status_code == 201 and r.json()["operator"]["isOperator"]
    token = client.post("/identity/login", json={"email": "jade@bishnoione.test", "password": "long enough 1"}).json()["accessToken"]
    op = {"Authorization": f"Bearer {token}"}
    assert client.get("/identity/me", headers=op).json()["staff"] == "admin"
    assert client.get("/platform/companies", headers=op).status_code == 200
    # Switched off: the Operations area closes; GetMeds' Jade never had it.
    client.put(f"/platform/operators/{r.json()['operator']['id']}", json={"isOperator": False}, headers=ana)
    assert client.get("/platform/companies", headers=op).status_code == 401
    assert client.get("/identity/me", headers=getmeds["jade"]["h"]).json()["staff"] is None


def test_the_staff_sign_in_is_closed_on_a_server(app, client):
    app.state.settings.environment = "production"
    try:
        r = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD})
        assert r.status_code == 403 and "Bishnoi One account" in r.json()["detail"]
    finally:
        app.state.settings.environment = "development"


def test_administrators_are_made_and_unmade_by_another_administrator(client, getmeds):
    owner, jade = getmeds["owner"], getmeds["jade"]
    h = owner["h"]
    body = client.get("/identity/company/administrators", headers=h).json()
    assert [a["email"] for a in body["administrators"]] == ["olive@getmeds.test"] and body["administrators"][0]["isMe"]
    # never yourself off, never the only one (also not by switching them off on People)
    assert client.put(f"/identity/company/administrators/{owner['id']}", json={"on": False}, headers=h).status_code == 409
    made = client.put(f"/identity/company/administrators/{jade['id']}", json={"on": True}, headers=h)
    assert made.status_code == 200, made.text
    assert {a["email"] for a in made.json()["administrators"]} == {"olive@getmeds.test", "jade@getmeds.test"}
    assert client.get("/identity/company", headers=jade["h"]).status_code == 200  # Jade opens the console now
    # Jade removes Olive; Olive's sign-ins end and she is no administrator any more
    gone = client.put(f"/identity/company/administrators/{owner['id']}", json={"on": False}, headers=jade["h"])
    assert gone.status_code == 200, gone.text
    assert client.get("/identity/me", headers=h).status_code == 401
    # Jade is now the only one: she can't be switched off on People either
    assert client.patch(f"/identity/access/people/{jade['id']}", json={"status": "suspended"}, headers=jade["h"]).status_code == 409
    log = client.get("/identity/company/activity", headers=jade["h"]).json()["entries"]
    assert [e["action"] for e in log[:2]] == ["company.administrator_removed", "company.administrator_added"]


def test_the_home_counts_people_sign_ins_security_and_access(client, getmeds):
    h = getmeds["owner"]["h"]
    client.delete(f"/identity/access/people/{getmeds['rio']['id']}", headers=h)
    o = client.get("/identity/company/overview", headers=h)
    assert o.status_code == 200, o.text
    body = o.json()
    assert body["people"] == {"active": 2, "off": 0, "inBin": 1, "administrators": 1, "noRole": 1, "noApps": 0}
    assert body["signIns"]["week"] == 2 and body["signIns"]["never"] == 0  # Olive and Jade signed in (the fixture)
    assert body["security"]["twoStepAdministrators"] == {"on": 0, "of": 1}
    apps = {a["key"]: a["people"] for a in body["apps"]}
    assert apps["crm"] == 2 and apps["pharmacy"] == 1  # Jade's grant + Olive, the administrator, opens every app
    assert any(e["action"] == "access.person_deleted" for e in body["recent"])
    assert client.get("/identity/company/overview", headers=getmeds["jade"]["h"]).status_code == 403


def test_people_reports_hold_people_never_money(client, getmeds):
    h = getmeds["owner"]["h"]
    keys = [r["key"] for r in client.get("/identity/company/reports", headers=h).json()["reports"]]
    assert keys == ["people", "sign-ins", "access-by-app", "roles", "security-events"]
    for key in keys:
        r = client.get(f"/identity/company/reports/{key}", headers=h)
        assert r.status_code == 200, (key, r.text)
        assert all(c["kind"] != "money" for c in r.json()["columns"])
    people = client.get("/identity/company/reports/people", headers=h).json()
    assert {row[1]["text"] for row in people["rows"]} == {"olive@getmeds.test", "jade@getmeds.test", "rio@getmeds.test"}
    signed = client.get("/identity/company/reports/sign-ins", headers=h).json()
    jade = next(row for row in signed["rows"] if row[1]["text"] == "jade@getmeds.test")
    assert jade[2]["raw"] == 1  # signed in once, by the fixture
    access = client.get("/identity/company/reports/access-by-app", headers=h).json()
    assert [c["label"] for c in access["columns"]][:2] == ["Name", "Role"]
    assert client.get("/identity/company/reports/revenue", headers=h).status_code == 404
