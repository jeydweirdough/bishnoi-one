"""Bulk actions on companies, contacts and follow-ups, and duplicate warnings."""

from datetime import UTC, datetime, timedelta

from tests.test_customers import activity, company, contact, crew  # noqa: F401  (crew is a fixture)


def me_id(client, headers) -> str:
    return client.get("/auth/me", headers=headers).json()["user"]["id"]


def test_bulk_status_checks_each_company(client, crew):
    mine = [company(client, crew["lia"], f"Lead {i}")["id"] for i in range(3)]
    sams = company(client, crew["sam"], "Sam Co")["id"]
    job = client.post("/companies/bulk", json={"ids": [*mine, sams, "nope"], "action": "status", "status": "customer"}, headers=crew["lia"]).json()
    assert (job["status"], job["total"], job["succeeded"], job["failed"]) == ("done", 5, 3, 2)
    assert {f["id"] for f in job["failures"]} == {sams, "nope"}
    assert {c["status"] for c in client.get("/companies", headers=crew["lia"]).json()["items"]} == {"customer"}
    # The job can be read back by whoever ran it, and nobody else.
    assert client.get(f"/jobs/{job['id']}", headers=crew["lia"]).json()["succeeded"] == 3
    assert client.get(f"/jobs/{job['id']}", headers=crew["ria"]).status_code == 404


def test_bulk_needs_the_permission(client, crew):
    ria_co = company(client, crew["ria"], "Ria Co")["id"]
    r = client.post("/companies/bulk", json={"ids": [ria_co], "action": "delete"}, headers=crew["ria"])
    assert r.status_code == 403  # reps don't delete


def test_bulk_owner_stays_within_reach(client, crew):
    ids = [company(client, crew["lia"], f"C{i}")["id"] for i in range(2)]
    rex = me_id(client, crew["rex"])
    sam = me_id(client, crew["sam"])
    assert client.post("/companies/bulk", json={"ids": ids, "action": "owner", "ownerId": sam}, headers=crew["lia"]).status_code == 422
    job = client.post("/companies/bulk", json={"ids": ids, "action": "owner", "ownerId": rex}, headers=crew["lia"]).json()
    assert job["succeeded"] == 2
    assert {c["owner"]["name"] for c in client.get("/companies", headers=crew["rex"]).json()["items"]} == {"Rex"}


def test_bulk_follow_up_for_each_owner(client, crew):
    ria_co = company(client, crew["ria"], "Ria Co")["id"]
    rex_co = company(client, crew["rex"], "Rex Co")["id"]
    body = {"ids": [ria_co, rex_co], "action": "follow_up", "followUp": {"title": "Check in", "dueOn": "2026-12-01"}, "toOwner": True}
    job = client.post("/companies/bulk", json=body, headers=crew["lia"]).json()
    assert job["succeeded"] == 2
    tasks = client.get("/activities", params={"kind": "task"}, headers=crew["lia"]).json()["items"]
    assert sorted((t["owner"]["name"], t["company"]["name"]) for t in tasks) == [("Rex", "Rex Co"), ("Ria", "Ria Co")]
    assert tasks[0]["at"].startswith("2026-12-01T01:00")  # 9 in the morning, Manila


def test_bulk_delete_skips_companies_with_contacts(client, crew):
    empty = company(client, crew["lia"], "Empty")["id"]
    busy = company(client, crew["lia"], "Busy")["id"]
    contact(client, crew["lia"], companyId=busy)
    job = client.post("/companies/bulk", json={"ids": [empty, busy], "action": "delete"}, headers=crew["lia"]).json()
    assert (job["succeeded"], job["failures"][0]["id"]) == (1, busy)


def test_bulk_follow_ups(client, crew):
    now = datetime.now(UTC)
    tasks = [activity(client, crew["ria"], kind="task", subject=f"T{i}", at=(now + timedelta(days=1)).isoformat())["id"] for i in range(2)]
    call = activity(client, crew["ria"])["id"]
    job = client.post("/activities/bulk", json={"ids": [*tasks, call], "action": "done"}, headers=crew["ria"]).json()
    assert (job["succeeded"], job["failures"][0]["id"]) == (2, call)  # a call isn't planned
    moved = client.post("/activities/bulk", json={"ids": tasks, "action": "due", "dueOn": "2026-12-24"}, headers=crew["ria"]).json()
    assert moved["succeeded"] == 2
    lia = me_id(client, crew["lia"])
    assert client.post("/activities/bulk", json={"ids": tasks, "action": "assign", "assigneeId": lia}, headers=crew["ria"]).status_code == 422
    assert client.post("/activities/bulk", json={"ids": tasks, "action": "assign", "assigneeId": lia}, headers=crew["lia"]).json()["succeeded"] == 2


# --- duplicates ---


def test_a_company_that_looks_like_another_is_flagged(client, crew):
    company(client, crew["sam"], "Acme Pharma", phone="0917 555 0101")
    r = client.post("/companies", json={"name": "ACME pharma"}, headers=crew["ria"])
    assert r.status_code == 409
    dup = r.json()["detail"]["duplicates"][0]
    # Ria can't see Sam's company: she learns it exists, not its details.
    assert (dup["name"], dup["teamName"], dup["phone"], dup["canOpen"]) == ("Acme Pharma", "South", None, False)
    by_phone = client.post("/companies", json={"name": "Other name", "phone": "09175550101"}, headers=crew["max"])
    assert by_phone.status_code == 409 and by_phone.json()["detail"]["duplicates"][0]["canOpen"] is True
    # It really is a different one: add it anyway.
    assert client.post("/companies", json={"name": "ACME pharma", "allowDuplicate": True}, headers=crew["ria"]).status_code == 201


def test_the_same_number_written_another_way_is_a_duplicate(client, crew):
    company(client, crew["sam"], "Acme Pharma", phone="0917 555 0101")
    for written in ("+63 917 555 0101", "(+63) 917-555-0101", "639175550101"):
        r = client.post("/companies", json={"name": "Other name", "phone": written}, headers=crew["sam"])
        assert r.status_code == 409, written
    acme = company(client, crew["lia"], "Beta Clinic")["id"]
    contact(client, crew["lia"], "Jo", companyId=acme, mobile="0918 222 3333")
    r = client.post("/contacts", json={"firstName": "Joan", "phone": "+639182223333"}, headers=crew["lia"])
    assert r.status_code == 409


def test_email_addresses_are_checked_and_kept_in_lower_case(client, crew):
    for bad in ("maria@", "maria@acme", "maria acme@acme.com", "maria@@acme.com"):
        r = client.post("/contacts", json={"firstName": "M", "email": bad}, headers=crew["lia"])
        assert r.status_code == 422, bad
    made = contact(client, crew["lia"], "Maria", email="Maria.Santos@Acme.COM")
    assert made["email"] == "maria.santos@acme.com"


def test_a_contact_that_looks_like_another_is_flagged(client, crew):
    acme = company(client, crew["lia"])["id"]
    contact(client, crew["lia"], "Maria", lastName="Santos", companyId=acme, email="maria@acme.com")
    same_name = client.post("/contacts", json={"firstName": "maria", "lastName": "santos", "companyId": acme}, headers=crew["lia"])
    same_email = client.post("/contacts", json={"firstName": "M", "email": "MARIA@acme.com"}, headers=crew["lia"])
    assert same_name.status_code == same_email.status_code == 409
    # The same name somewhere else is a different person.
    assert client.post("/contacts", json={"firstName": "Maria", "lastName": "Santos"}, headers=crew["lia"]).status_code == 201
