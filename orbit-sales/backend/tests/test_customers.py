"""Companies, contacts and activities, and whose of them each role reaches."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import Role, RolePermission, Team, User
from app.security import hash_password
from tests.conftest import PASSWORD, bearer, role_id, sign_in


@pytest.fixture
def crew(app, client) -> dict[str, dict]:
    """Two teams. North: Ria and Rex (salespeople), Lia (their lead). South: Sam
    (salesperson). Max has a Team Lead's permissions over every team (a role an
    admin made, "Director"). Returns each person's sign-in headers."""
    with app.state.sessions() as db:
        north, south = Team(name="North"), Team(name="South")
        lead = db.get(Role, role_id(db, "Team Lead"))
        director = Role(name="Director", scope="all", grants=[RolePermission(permission=p) for p in lead.permissions])
        db.add_all([north, south, director])
        db.flush()
        people = {
            "ria": ("Salesperson", north.id),
            "rex": ("Salesperson", north.id),
            "lia": ("Team Lead", north.id),
            "sam": ("Salesperson", south.id),
            "max": ("Director", None),
        }
        for name, (role, team) in people.items():
            db.add(User(email=f"{name}@example.com", full_name=name.title(), password_hash=hash_password(PASSWORD), role_id=role_id(db, role), team_id=team))
        db.commit()
    return {name: bearer(sign_in(client, f"{name}@example.com")) for name in people}


def company(client, headers, name="Acme", **extra) -> dict:
    r = client.post("/companies", json={"name": name, **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def contact(client, headers, first="Maria", **extra) -> dict:
    r = client.post("/contacts", json={"firstName": first, **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def activity(client, headers, **body) -> dict:
    r = client.post("/activities", json={"kind": "call", "subject": "Intro call", **body}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def names(client, headers, path="/companies") -> set[str]:
    return {i["name"] for i in client.get(path, headers=headers).json()["items"]}


# --- reach ---


def test_each_role_sees_its_own_its_teams_or_everything(client, crew):
    company(client, crew["ria"], "Ria Co")
    company(client, crew["rex"], "Rex Co")
    company(client, crew["sam"], "Sam Co")
    assert names(client, crew["ria"]) == {"Ria Co"}  # own
    assert names(client, crew["lia"]) == {"Ria Co", "Rex Co"}  # her team's
    assert names(client, crew["max"]) == {"Ria Co", "Rex Co", "Sam Co"}  # everyone's


def test_out_of_reach_is_not_found_not_forbidden(client, crew):
    sams = company(client, crew["sam"], "Sam Co")
    for method, extra in (("get", {}), ("patch", {"json": {"name": "Mine now"}}), ("delete", {})):
        r = getattr(client, method)(f"/companies/{sams['id']}", headers=crew["ria"], **extra)
        assert r.status_code in (403, 404), method  # delete: reps may not delete at all
    assert client.get(f"/companies/{sams['id']}", headers=crew["ria"]).status_code == 404
    assert client.patch(f"/companies/{sams['id']}", json={"name": "x"}, headers=crew["ria"]).status_code == 404


def test_giving_a_record_away_stays_within_reach(client, crew):
    ria_id = client.get("/auth/me", headers=crew["ria"]).json()["user"]["id"]
    sam_id = client.get("/auth/me", headers=crew["sam"]).json()["user"]["id"]
    # A rep reaches only herself, so she can't give records to anyone else.
    r = client.post("/companies", json={"name": "X", "ownerId": sam_id}, headers=crew["ria"])
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "ownerId"]
    assert [p["name"] for p in client.get("/people/assignable", headers=crew["ria"]).json()] == ["Ria"]
    # Her lead can give it to anyone in North, and the record takes their team.
    lias = company(client, crew["lia"], "Lead Co", ownerId=ria_id)
    assert (lias["owner"]["name"], lias["team"]["name"]) == ("Ria", "North")
    assert client.post("/companies", json={"name": "Y", "ownerId": sam_id}, headers=crew["lia"]).status_code == 422
    # The manager can give it to Sam, and then it's South's.
    moved = client.patch(f"/companies/{lias['id']}", json={"ownerId": sam_id}, headers=crew["max"]).json()
    assert moved["team"]["name"] == "South"
    assert client.get(f"/companies/{lias['id']}", headers=crew["ria"]).status_code == 404


def test_permissions_still_apply_within_reach(client, crew):
    mine = company(client, crew["ria"], "Ria Co")
    assert mine["can"] == {"edit": True, "delete": False}  # reps don't delete
    assert client.delete(f"/companies/{mine['id']}", headers=crew["ria"]).status_code == 403
    assert client.get(f"/companies/{mine['id']}", headers=crew["lia"]).json()["can"] == {"edit": True, "delete": True}


# --- companies ---


def test_company_fields_are_checked(client, crew):
    assert client.post("/companies", json={"name": ""}, headers=crew["ria"]).status_code == 422
    assert client.post("/companies", json={"name": "A", "email": "nope"}, headers=crew["ria"]).status_code == 422
    assert client.post("/companies", json={"name": "A", "website": "not a site"}, headers=crew["ria"]).status_code == 422
    assert client.post("/companies", json={"name": "A", "status": "friend"}, headers=crew["ria"]).status_code == 422
    made = company(client, crew["ria"], "A", status="customer", industry="", email="Sales@Acme.COM")
    assert (made["status"], made["industry"], made["email"]) == ("customer", None, "sales@acme.com")


def test_search_filter_and_page(client, crew):
    for name, city in (("Alpha", "Cebu"), ("Beta", "Manila"), ("Gamma", "Cebu")):
        company(client, crew["max"], name, city=city)
    cebu = client.get("/companies", params={"q": "cebu"}, headers=crew["max"]).json()
    assert cebu["total"] == 2 and [c["name"] for c in cebu["items"]] == ["Alpha", "Gamma"]
    page = client.get("/companies", params={"limit": 1, "offset": 1}, headers=crew["max"]).json()
    assert page["total"] == 3 and page["items"][0]["name"] == "Beta"


def test_a_company_with_contacts_cant_be_deleted(client, crew):
    acme = company(client, crew["lia"])
    maria = contact(client, crew["lia"], companyId=acme["id"])
    r = client.delete(f"/companies/{acme['id']}", headers=crew["lia"])
    assert r.status_code == 409 and "1 contact" in r.json()["detail"]
    assert client.delete(f"/contacts/{maria['id']}", headers=crew["lia"]).status_code == 204
    assert client.delete(f"/companies/{acme['id']}", headers=crew["lia"]).status_code == 204


# --- contacts ---


def test_contacts_belong_to_a_company_in_reach(client, crew):
    acme = company(client, crew["ria"])
    sams = company(client, crew["sam"], "Sam Co")
    maria = contact(client, crew["ria"], "Maria", lastName="Santos", companyId=acme["id"], email="maria@acme.com")
    assert (maria["name"], maria["company"]["name"]) == ("Maria Santos", "Acme")
    r = client.post("/contacts", json={"firstName": "X", "companyId": sams["id"]}, headers=crew["ria"])
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "companyId"]
    detail = client.get(f"/companies/{acme['id']}", headers=crew["ria"]).json()
    assert [c["name"] for c in detail["contacts"]] == ["Maria Santos"] and detail["contactCount"] == 1
    # Found by their company's name too.
    assert names(client, crew["ria"], "/contacts?q=acme") == {"Maria Santos"}


def test_deleting_a_contact_keeps_what_belongs_to_the_company(client, crew):
    acme = company(client, crew["lia"])
    maria = contact(client, crew["lia"], companyId=acme["id"])
    solo = contact(client, crew["lia"], "Solo")
    kept = activity(client, crew["lia"], contactId=maria["id"])  # takes Acme along
    gone = activity(client, crew["lia"], contactId=solo["id"])
    assert kept["company"]["name"] == "Acme"
    client.delete(f"/contacts/{maria['id']}", headers=crew["lia"])
    client.delete(f"/contacts/{solo['id']}", headers=crew["lia"])
    ids = {a["id"] for a in client.get("/activities", headers=crew["lia"]).json()["items"]}
    assert kept["id"] in ids and gone["id"] not in ids


# --- activities ---


def test_logged_kinds_are_done_planned_kinds_wait(client, crew):
    call = activity(client, crew["ria"], kind="call", direction="out", durationMinutes=12)
    assert call["isDone"] and not call["isPlanned"] and call["durationMinutes"] == 12
    task = activity(client, crew["ria"], kind="task", subject="Send the proposal", at=(datetime.now(UTC) + timedelta(days=2)).isoformat())
    assert task["isPlanned"] and not task["isDone"] and not task["isOverdue"]
    # A note never has a direction or a duration, whatever is sent.
    note = activity(client, crew["ria"], kind="note", subject="Prefers email", direction="in", durationMinutes=5)
    assert (note["direction"], note["durationMinutes"]) == (None, None)

    done = client.patch(f"/activities/{task['id']}", json={"done": True}, headers=crew["ria"]).json()
    assert done["isDone"]
    again = client.patch(f"/activities/{task['id']}", json={"done": False}, headers=crew["ria"]).json()
    assert not again["isDone"]


def test_whats_due(client, crew):
    now = datetime.now(UTC)
    activity(client, crew["ria"], kind="task", subject="late", at=(now - timedelta(days=2)).isoformat())
    activity(client, crew["ria"], kind="task", subject="later", at=(now + timedelta(days=3)).isoformat())
    activity(client, crew["ria"], kind="meeting", subject="done already", at=(now - timedelta(days=1)).isoformat(), done=True)
    counts = client.get("/activities/summary", headers=crew["ria"]).json()
    assert (counts["overdue"], counts["upcoming"], counts["open"]) == (1, 1, 2)
    activity(client, crew["ria"], kind="meeting", subject="a meeting", at=(now + timedelta(days=3)).isoformat())
    tasks_only = client.get("/activities/summary", params={"kind": "task"}, headers=crew["ria"]).json()
    assert (tasks_only["upcoming"], tasks_only["open"]) == (1, 2)
    overdue = client.get("/activities", params={"state": "overdue"}, headers=crew["ria"]).json()["items"]
    assert [a["subject"] for a in overdue] == ["late"] and overdue[0]["isOverdue"]


def test_a_time_without_a_zone_is_the_companys_own(client, crew):
    # 09:00 in Manila is 01:00 UTC.
    task = activity(client, crew["ria"], kind="task", subject="Morning call", at="2026-10-01T09:00")
    assert task["at"].startswith("2026-10-01T01:00:00")


def test_activities_link_only_within_reach(client, crew):
    sams = company(client, crew["sam"], "Sam Co")
    r = client.post("/activities", json={"kind": "note", "subject": "x", "companyId": sams["id"]}, headers=crew["ria"])
    assert r.status_code == 422
    acme = company(client, crew["ria"])
    other = company(client, crew["ria"], "Other")
    maria = contact(client, crew["ria"], companyId=acme["id"])
    r = client.post("/activities", json={"kind": "note", "subject": "x", "companyId": other["id"], "contactId": maria["id"]}, headers=crew["ria"])
    assert r.status_code == 422 and "another customer" in r.json()["detail"][0]["msg"]


def test_activities_follow_reach_too(client, crew):
    activity(client, crew["ria"], subject="ria's")
    activity(client, crew["sam"], subject="sam's")
    subjects = lambda who: {a["subject"] for a in client.get("/activities", headers=crew[who]).json()["items"]}  # noqa: E731
    assert subjects("ria") == {"ria's"}
    assert subjects("lia") == {"ria's"}
    assert subjects("max") == {"ria's", "sam's"}


def test_changes_are_audited(client, crew, ana):
    acme = company(client, crew["lia"])
    client.patch(f"/companies/{acme['id']}", json={"status": "customer", "phone": "123"}, headers=crew["lia"])
    task = activity(client, crew["lia"], kind="task", subject="Follow up", companyId=acme["id"])
    client.patch(f"/activities/{task['id']}", json={"done": True}, headers=crew["lia"])
    log = client.get("/admin/audit", params={"limit": 3}, headers=ana).json()["items"]
    assert [e["action"] for e in log] == ["activity.completed", "activity.created", "company.updated"]
    assert sorted(log[2]["fields"]) == ["phone", "status"]


# --- customer types ---


def test_an_administrator_keeps_the_customer_types(client, crew, ana):
    assert [t["code"] for t in client.get("/customer-types", headers=crew["ria"]).json()] == ["prospect", "customer", "partner", "inactive"]
    assert client.post("/admin/customer-types", json={"name": "Distributor"}, headers=crew["max"]).status_code == 403
    types = client.post("/admin/customer-types", json={"name": "Key account", "color": "amber"}, headers=ana).json()
    key = next(t for t in types if t["name"] == "Key account")
    assert key["code"] == "key_account" and key["isActive"]
    assert client.post("/admin/customer-types", json={"name": "key ACCOUNT"}, headers=ana).status_code == 422

    acme = company(client, crew["ria"], status="key_account")
    assert acme["status"] == "key_account"
    assert company(client, crew["ria"], "Beta")["status"] == "prospect"  # the first on the list
    assert client.post("/companies", json={"name": "Gamma", "status": "nonsense"}, headers=crew["ria"]).status_code == 422

    assert client.delete("/admin/customer-types/key_account", headers=ana).status_code == 409  # in use
    client.patch("/admin/customer-types/key_account", json={"isActive": False, "name": "Key acct"}, headers=ana)
    assert client.patch(f"/companies/{acme['id']}", json={"name": "Acme 2"}, headers=crew["ria"]).status_code == 200  # keeps its type
    assert client.post("/companies", json={"name": "Delta", "status": "key_account"}, headers=crew["ria"]).status_code == 422  # not offered
    assert client.delete("/admin/customer-types/partner", headers=ana).status_code == 204
