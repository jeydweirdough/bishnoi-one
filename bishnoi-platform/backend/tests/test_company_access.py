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
    # Everyone who may open the module, with their role here (if any) and whether they're switched on (R2).
    assert {"email": "jade@getmeds.test", "role": "Medical rep", "admin": False, "active": True, "details": {}} in crm["people"]
    assert {"email": "rio@getmeds.test", "role": None, "admin": False, "active": True, "details": {}} in crm["people"]
    # Pharmacy is told the roles too: only Rio may open it, with no role from here yet.
    assert notes["https://pharmacy-api.example.com/platform/roles"]["people"] == [{"email": "rio@getmeds.test", "role": None, "admin": False, "active": True, "details": {}}]


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


def test_staff_open_the_console_with_their_bishnoi_one_account(client, ana, getmeds):
    """One sign-in (decided 2026-10-24): a Bishnoi One account whose email is staff's acts as that staff member."""
    from tests.conftest import PASSWORD

    token = client.post("/identity/login", json={"email": "ana@example.com", "password": PASSWORD}).json()["accessToken"]  # Ana is an operator
    ana_account = {"Authorization": f"Bearer {token}"}
    assert client.get("/identity/me", headers=ana_account).json()["staff"] == "admin"
    assert client.get("/platform/companies", headers=ana_account).status_code == 200
    # someone who isn't staff gets nothing of the console's
    assert client.get("/identity/me", headers=getmeds["jade"]["h"]).json()["staff"] is None
    assert client.get("/platform/companies", headers=getmeds["jade"]["h"]).status_code == 401


def test_a_company_administrator_adds_and_keeps_their_people(client, getmeds):
    """R2 (decided 2026-10-26): people are added, changed, switched off and given a password on the
    Platform by their company's own administrators, once for every module."""
    owner = getmeds["owner"]["h"]
    r = client.post("/identity/access/people", json={"fullName": "Nina New", "email": "nina@getmeds.test", "title": "Pharmacist", "apps": ["crm"]}, headers=owner)
    assert r.status_code == 201, r.text
    nina = r.json()["person"]
    assert nina["status"] == "active" and r.json()["hasPassword"] is False
    assert client.post("/identity/access/people", json={"fullName": "Again", "email": "NINA@getmeds.test"}, headers=owner).status_code == 422  # one email, once

    made = client.post(f"/identity/access/people/{nina['id']}/password", json={}, headers=owner).json()["password"]
    assert made and client.post("/identity/login", json={"email": "nina@getmeds.test", "password": made}).status_code == 200

    assert client.patch(f"/identity/access/people/{nina['id']}", json={"title": "Head pharmacist"}, headers=owner).json()["person"]["title"] == "Head pharmacist"
    assert client.patch(f"/identity/access/people/{nina['id']}", json={"status": "suspended"}, headers=owner).json()["person"]["status"] == "suspended"
    assert client.post("/identity/login", json={"email": "nina@getmeds.test", "password": made}).status_code != 200  # switched off: no sign-in
    # Not themselves, and not by someone who isn't a company administrator.
    assert client.patch(f"/identity/access/people/{getmeds['owner']['id']}", json={"status": "suspended"}, headers=owner).status_code == 409
    others = [k for k in getmeds if k not in ("company", "owner")]
    if others:
        assert client.post("/identity/access/people", json={"fullName": "X Y", "email": "xy@getmeds.test"}, headers=getmeds[others[0]]["h"]).status_code == 403



def test_switching_someone_off_tells_every_module(client, getmeds, modules):
    """R2: switched off on the Platform, switched off in each module they may open (which ends their sessions there)."""
    h = getmeds["owner"]["h"]
    modules.clear()
    assert client.patch(f"/identity/access/people/{getmeds['rio']['id']}", json={"status": "suspended"}, headers=h).status_code == 200
    key = client.get("/pass/key").json()["publicKey"]
    notes = {url: claims_of(body["pass"], key) for url, body in modules}
    for url in ("https://crm-api.example.com/platform/roles", "https://pharmacy-api.example.com/platform/roles"):
        rio = next(p for p in notes[url]["people"] if p["email"] == "rio@getmeds.test")
        assert rio["active"] is False, url


def test_saved_reports_are_kept_once_and_shared_safely(client, getmeds):
    """Saved reports (app/routers/saved_reports.py): the owner keeps their choices; shared ones show
    to the company; only the owner changes them; a company administrator may remove one."""
    jade, owner = getmeds["jade"]["h"], getmeds["owner"]["h"]
    made = client.post("/identity/reports", json={"app": "crm", "baseKey": "pipeline", "name": "My pipeline", "definition": {"columns": ["stage"]}}, headers=jade)
    assert made.status_code == 201, made.text
    rid = made.json()["id"]
    assert [r["name"] for r in client.get("/identity/reports?app=crm", headers=jade).json()] == ["My pipeline"]
    assert client.get("/identity/reports?app=crm", headers=owner).json() == []  # not shared yet
    assert client.patch(f"/identity/reports/{rid}", json={"shared": True}, headers=jade).json()["shared"] is True
    seen = client.get("/identity/reports?app=crm", headers=owner).json()
    assert seen[0]["name"] == "My pipeline" and seen[0]["mine"] is False and seen[0]["owner"] == "Jade Madigal"
    assert client.patch(f"/identity/reports/{rid}", json={"name": "Theirs"}, headers=owner).status_code == 404  # not the owner
    assert client.get("/identity/reports?app=finance", headers=jade).json() == []  # one module's reports only
    assert client.delete(f"/identity/reports/{rid}", headers=owner).status_code == 204  # a company administrator may


def test_deleting_a_person_puts_them_in_the_recycle_bin_and_restore_brings_them_back(client, getmeds):
    h, jade = getmeds["owner"]["h"], getmeds["jade"]
    assert client.delete(f"/identity/access/people/{getmeds['owner']['id']}", headers=h).status_code == 409  # never yourself
    r = client.delete(f"/identity/access/people/{jade['id']}", headers=h)
    assert r.status_code == 200, r.text
    assert client.get("/identity/me", headers=jade["h"]).status_code == 401  # her sign-ins ended
    body = client.get("/identity/access", headers=h).json()
    assert jade["id"] not in [p["id"] for p in body["people"]] and body["inBin"] == 1
    bin_ = client.get("/identity/access/bin", headers=h).json()["people"]
    assert [p["email"] for p in bin_] == ["jade@getmeds.test"] and bin_[0]["status"] == "suspended"
    # nothing is done to someone in the bin but restoring them; her email isn't taken by someone new either
    assert client.patch(f"/identity/access/people/{jade['id']}", json={"status": "active"}, headers=h).status_code == 409
    again = client.post("/identity/access/people", json={"fullName": "Jade Again", "email": "jade@getmeds.test"}, headers=h)
    assert again.status_code == 422 and "recycle bin" in again.text
    assert client.post(f"/identity/access/people/{jade['id']}/restore", headers=h).status_code == 200
    body = client.get("/identity/access", headers=h).json()
    back = next(p for p in body["people"] if p["id"] == jade["id"])
    assert back["status"] == "suspended" and body["inBin"] == 0  # back on People, switched off until switched on
    assert client.patch(f"/identity/access/people/{jade['id']}", json={"status": "active"}, headers=h).status_code == 200
    log = [e["action"] for e in client.get("/identity/company/activity", headers=h).json()["entries"]]
    assert "access.person_deleted" in log and "access.person_restored" in log


def test_each_apps_details_about_a_person_are_kept_here_and_sent(client, getmeds):
    from app import access_roles
    from app.models import Application, Company

    h, jade = getmeds["owner"]["h"], getmeds["jade"]
    r = client.patch(f"/identity/access/people/{jade['id']}", json={"appDetails": {"crm": {"employeeId": "GM-0042"}, "pharmacy": {"licenseNo": "PRC-77"}}}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["person"]["appDetails"] == {"crm": {"employeeId": "GM-0042"}, "pharmacy": {"licenseNo": "PRC-77"}}
    assert client.patch(f"/identity/access/people/{jade['id']}", json={"appDetails": {"crm": {"shoeSize": "9"}}}, headers=h).status_code == 422
    # cleared by sending it empty
    r = client.patch(f"/identity/access/people/{jade['id']}", json={"appDetails": {"pharmacy": {"licenseNo": ""}}}, headers=h)
    assert r.json()["person"]["appDetails"] == {"crm": {"employeeId": "GM-0042"}}
    # what the CRM is told about her
    app_ = client.app
    with app_.state.sessions() as db:
        company = db.get(Company, getmeds["company"]["id"])
        crm = db.query(Application).filter(Application.key == "crm").one()
        from app.passes import public_key  # noqa: F401  (signing works in tests)
        token = access_roles.roles_note(db, app_.state.settings, company, crm)
    import base64, json
    claims = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
    who = next(p for p in claims["people"] if p["email"] == "jade@getmeds.test")
    assert who["details"] == {"employeeId": "GM-0042"}
