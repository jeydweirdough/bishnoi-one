"""Access in one place (decided 2026-10-23): a company's administrator makes its
roles here, for every module, and gives each person one; the modules are sent
the roles, signed, and each sign-in pass carries the person's role."""

import httpx
import pytest

from app import access_roles
from tests.conftest import app_id, make_company
from tests.test_identity import claims_of

CATALOGS = {
    "crm": {
        "areas": [{"key": "customers", "name": "Customers", "group": "CRM", "actions": [
            {"key": "view", "label": "View", "permission": "customers.view"},
            {"key": "edit", "label": "Edit", "permission": "customers.edit"},
        ]}],
        "scopes": [{"key": "own", "label": "Their own records"}, {"key": "team", "label": "Their team's records"}, {"key": "all", "label": "Every record"}],
    },
    "pharmacy": {
        "areas": [{"key": "prescriptions", "name": "Prescriptions", "group": "Work", "actions": [
            {"key": "view", "label": "View", "permission": "prescriptions.view"},
        ]}],
        "scopes": [],
    },
}
TODAY = {  # the roles each module has before the platform keeps them
    "crm": [
        {"name": "Administrator", "description": "Everything", "scope": "all", "permissions": ["customers.view", "customers.edit"], "isSystem": True},
        {"name": "Salesperson", "description": "Their own customers", "scope": "own", "permissions": ["customers.view"], "isSystem": False},
    ],
    "pharmacy": [
        {"name": "Administrator", "description": None, "scope": None, "permissions": ["prescriptions.view"], "isSystem": True},
        {"name": "Pharmacist", "description": None, "scope": None, "permissions": ["prescriptions.view"], "isSystem": False},
    ],
}


class Answer:
    def __init__(self, status_code, body=None):
        self.status_code, self._body = status_code, body

    def json(self):
        return self._body


@pytest.fixture
def modules(monkeypatch, client, ana):
    """CRM and Pharmacy with API addresses, their catalogs, and what was sent to them (at once, not on a thread)."""
    for key in ("crm", "pharmacy"):
        client.patch(f"/platform/applications/{app_id(client, ana, key)}", json={"apiUrl": f"https://{key}-api.example.com"}, headers=ana)
    monkeypatch.setattr(access_roles, "catalog", lambda app: CATALOGS.get(app.key))
    monkeypatch.setattr(access_roles, "push", lambda sessions, settings, company_id: access_roles._send(sessions, settings, company_id))
    sent: list[tuple[str, dict]] = []

    def post(url, json=None, timeout=None):
        sent.append((url, json))
        if url.endswith("/platform/roles/export"):
            return Answer(200, {"roles": TODAY["crm" if "crm-api" in url else "pharmacy"]})
        return Answer(204)

    monkeypatch.setattr(httpx, "post", post)
    return sent


def person(client, ana, company, name, email, apps=(), admin=False) -> dict:
    p = client.post("/platform/users", json={"companyId": company["id"], "fullName": name, "email": email, "isCompanyAdmin": admin}, headers=ana).json()["user"]
    for key, role in apps:
        client.put(f"/platform/users/{p['id']}/applications/{app_id(client, ana, key)}", json={"role": role}, headers=ana)
    password = client.post(f"/platform/users/{p['id']}/password", json={}, headers=ana).json()["password"]
    token = client.post("/identity/login", json={"email": email, "password": password}).json()["accessToken"]
    return {"id": p["id"], "h": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def getmeds(client, ana, modules) -> dict:
    c = make_company(client, ana)
    return {
        "company": c,
        "owner": person(client, ana, c, "Olive Owner", "olive@getmeds.test", admin=True),
        "jade": person(client, ana, c, "Jade Madigal", "jade@getmeds.test", apps=(("crm", "Salesperson"),)),
        "rio": person(client, ana, c, "Rio Santos", "rio@getmeds.test", apps=(("crm", "Salesperson"), ("pharmacy", "Pharmacist"))),
    }


def test_only_a_company_administrator_manages_access(client, getmeds):
    assert client.get("/identity/access", headers=getmeds["jade"]["h"]).status_code == 403
    r = client.get("/identity/access", headers=getmeds["owner"]["h"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert [m["key"] for m in body["modules"]] == ["crm", "pharmacy"]
    assert body["modules"][0]["scopes"][0]["key"] == "own"
    # Jade and Rio have a role in an application but none here yet
    assert set(body["toChoose"]) == {getmeds["jade"]["id"], getmeds["rio"]["id"]}


def test_a_role_holds_several_modules_with_a_scope_each(client, getmeds):
    h = getmeds["owner"]["h"]
    r = client.post("/identity/access/roles", json={
        "name": "Medical rep", "permissions": {"crm": ["customers.view", "customers.edit"], "pharmacy": ["prescriptions.view"]}, "scopes": {"crm": "team"},
    }, headers=h)
    assert r.status_code == 201, r.text
    role = r.json()
    assert role["permissions"] == {"crm": ["customers.edit", "customers.view"], "pharmacy": ["prescriptions.view"]}
    assert role["scopes"] == {"crm": "team"}
    # what a module doesn't declare can't be given
    bad = client.post("/identity/access/roles", json={"name": "Odd", "permissions": {"crm": ["deals.fly"]}}, headers=h)
    assert bad.status_code == 422 and "deals.fly" in bad.text
    # Administrator is the role with everything
    assert client.post("/identity/access/roles", json={"name": "administrator"}, headers=h).status_code == 422
    # a module where no scope was chosen gets the narrowest
    narrow = client.post("/identity/access/roles", json={"name": "Viewer", "permissions": {"crm": ["customers.view"]}}, headers=h).json()
    assert narrow["scopes"] == {"crm": "own"}


def test_giving_a_role_tells_every_module_signed(client, getmeds, modules):
    h = getmeds["owner"]["h"]
    role = client.post("/identity/access/roles", json={"name": "Medical rep", "permissions": {"crm": ["customers.view"]}, "scopes": {"crm": "own"}}, headers=h).json()
    modules.clear()
    r = client.put(f"/identity/access/people/{getmeds['jade']['id']}/role", json={"roleId": role["id"]}, headers=h)
    assert r.status_code == 200, r.text
    key = client.get("/pass/key").json()["publicKey"]
    notes = {url: claims_of(body["pass"], key) for url, body in modules}
    crm = notes["https://crm-api.example.com/platform/roles"]
    assert crm["kind"] == "roles" and crm["aud"] == "crm" and crm["slug"] == getmeds["company"]["slug"]
    assert {"name": "Medical rep", "description": None, "scope": "own", "permissions": ["customers.view"], "admin": False} in crm["roles"]
    assert crm["people"] == [{"email": "jade@getmeds.test", "role": "Medical rep", "admin": False}]
    # Pharmacy is told the roles too, with nobody holding one there (Jade doesn't have it)
    assert notes["https://pharmacy-api.example.com/platform/roles"]["people"] == []


def test_the_pass_carries_the_role_given_here(client, getmeds):
    h = getmeds["owner"]["h"]
    role = client.post("/identity/access/roles", json={"name": "Medical rep", "permissions": {"crm": ["customers.view"]}}, headers=h).json()
    client.put(f"/identity/access/people/{getmeds['jade']['id']}/role", json={"roleId": role["id"]}, headers=h)
    r = client.post("/identity/pass", json={"app": "crm", "returnTo": "http://localhost:4302/auth/platform"}, headers=getmeds["jade"]["h"])
    claims = claims_of(r.json()["pass"], client.get("/pass/key").json()["publicKey"])
    assert claims["role"] == "Medical rep"  # not the Salesperson on her grant
    assert claims["roleDef"] == {"name": "Medical rep", "description": None, "scope": "own", "permissions": ["customers.view"], "admin": False}
    assert client.get("/identity/me", headers=getmeds["jade"]["h"]).json()["role"] == "Medical rep"


def test_importing_the_roles_each_module_has_today(client, getmeds):
    h = getmeds["owner"]["h"]
    r = client.post("/identity/access/import", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"rolesMade": 3, "peopleGiven": 1, "toChoose": 1, "unreachable": []}
    body = client.get("/identity/access", headers=h).json()
    roles = {x["name"]: x for x in body["roles"]}
    assert roles["Administrator"]["isAdmin"] is True
    assert roles["Salesperson"]["permissions"] == {"crm": ["customers.view"]} and roles["Salesperson"]["scopes"] == {"crm": "own"}
    people = {p["email"]: p for p in body["people"]}
    assert people["jade@getmeds.test"]["roleId"] == roles["Salesperson"]["id"]
    # Rio is a Salesperson in the CRM and a Pharmacist in Pharmacy: the administrator chooses
    assert people["rio@getmeds.test"]["roleId"] is None and body["toChoose"] == [getmeds["rio"]["id"]]
    # done again, nothing is made twice
    assert client.post("/identity/access/import", headers=h).json()["rolesMade"] == 0


def test_a_role_someone_holds_isnt_deleted_and_somebody_keeps_everything(client, getmeds):
    h = getmeds["owner"]["h"]
    admin = client.post("/identity/access/roles", json={"name": "Administrator", "isAdmin": True}, headers=h).json()
    rep = client.post("/identity/access/roles", json={"name": "Rep", "permissions": {"crm": ["customers.view"]}}, headers=h).json()
    client.put(f"/identity/access/people/{getmeds['owner']['id']}/role", json={"roleId": admin["id"]}, headers=h)
    client.put(f"/identity/access/people/{getmeds['jade']['id']}/role", json={"roleId": rep["id"]}, headers=h)
    assert client.delete(f"/identity/access/roles/{rep['id']}", headers=h).status_code == 409
    # the only person with everything can't lose it, nor can the role stop being everything
    assert client.put(f"/identity/access/people/{getmeds['owner']['id']}/role", json={"roleId": rep["id"]}, headers=h).status_code == 409
    assert client.patch(f"/identity/access/roles/{admin['id']}", json={"isAdmin": False, "name": "Boss"}, headers=h).status_code == 409


def test_giving_and_taking_a_module(client, getmeds):
    h, jade = getmeds["owner"]["h"], getmeds["jade"]["id"]
    assert client.put(f"/identity/access/people/{jade}/apps/pharmacy", headers=h).status_code == 200
    apps = next(p for p in client.get("/identity/access", headers=h).json()["people"] if p["id"] == jade)["apps"]
    assert {a["key"] for a in apps} == {"crm", "pharmacy"}
    assert client.delete(f"/identity/access/people/{jade}/apps/pharmacy", headers=h).status_code == 204
    assert client.put(f"/identity/access/people/{jade}/apps/finance", headers=h).status_code == 404  # GetMeds doesn't have it
