"""Field work: agents visit their doctors and collect what they owe; balances
come from accounting; each agent's month is measured against the goals an
administrator set."""

import pytest
from sqlalchemy import select

from app.models import CustomerType, Role, Team, User
from app.security import hash_password
from tests.conftest import PASSWORD, bearer, role_id, sign_in

MONTH = "2026-09"
# Field agents' visits always carry where they were logged.
HERE = {"latitude": 14.5547, "longitude": 121.0244, "accuracyM": 15}


@pytest.fixture
def field(app, client, ana) -> dict[str, dict]:
    """North: Fay and Finn (field agents) and Lia (their Team Lead). South: Sol
    (field agent). Ana is the Administrator. The company works as GetMeds does:
    its field agents visit doctors (Settings → Terms, the Doctor type on)."""
    with app.state.sessions() as db:
        from app.pricing import sales_settings
        from app.terms import PHARMA

        db.scalar(select(CustomerType).where(CustomerType.code == "doctor")).is_active = True
        sales_settings(db).terms = dict(PHARMA)
        north, south = Team(name="North"), Team(name="South")
        db.add_all([north, south])
        db.flush()
        people = {"fay": ("Field agent", north.id), "finn": ("Field agent", north.id), "lia": ("Team Lead", north.id), "sol": ("Field agent", south.id)}
        for name, (role, team) in people.items():
            db.add(User(email=f"{name}@example.com", full_name=name.title(), password_hash=hash_password(PASSWORD), role_id=role_id(db, role), team_id=team))
        db.commit()
    out = {name: bearer(sign_in(client, f"{name}@example.com")) for name in people}
    out["ana"] = ana
    out["ids"] = {name: client.get("/auth/me", headers=out[name]).json()["user"]["id"] for name in people}
    return out


def doctor(client, field, name: str, agent: str) -> dict:
    """A doctor given to an agent (agents don't add customers; their lead or an admin does)."""
    r = client.post("/companies", json={"name": name, "status": "doctor", "ownerId": field["ids"][agent], "allowDuplicate": True}, headers=field["ana"])
    assert r.status_code == 201, r.text
    return r.json()


def visit(client, headers, doc: dict, **body) -> dict:
    r = client.post("/visits", json={"companyId": doc["id"], "outcome": "promised", "visitedAt": f"{MONTH}-10T10:00:00", "location": HERE, **body}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_the_field_agent_role_and_the_doctor_type_are_there(app):
    with app.state.sessions() as db:
        agent = db.scalar(select(Role).where(Role.name == "Field agent"))
        assert agent.scope == "own"
        assert {"visits.create", "customers.view", "customers.edit"} <= agent.permissions
        assert "customers.create" not in agent.permissions and "goals.view" not in agent.permissions
        assert db.get(CustomerType, "doctor").name == "Doctor"
        assert {"visits.view", "goals.view"} <= db.scalar(select(Role).where(Role.name == "Team Lead")).permissions


def test_an_agent_logs_visits_to_their_own_doctors_only(client, field):
    mine, sols = doctor(client, field, "Dr. Cruz", "fay"), doctor(client, field, "Dr. Reyes", "sol")
    v = visit(client, field["fay"], mine, outcome="collected", amountCentavos=150000, receiptNo="OR-1")
    assert (v["outcome"], v["amountCentavos"], v["receiptNo"], v["owner"]["name"]) == ("collected", 150000, "OR-1", "Fay")
    r = client.post("/visits", json={"companyId": sols["id"], "outcome": "not_in"}, headers=field["fay"])
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "companyId"]
    # Her own visits; her lead sees the team's; Sol sees none of North's.
    assert client.get("/visits", headers=field["fay"]).json()["total"] == 1
    assert client.get("/visits", headers=field["lia"]).json()["total"] == 1
    assert client.get("/visits", headers=field["sol"]).json()["total"] == 0


def test_only_a_collection_has_an_amount(client, field):
    doc = doctor(client, field, "Dr. Cruz", "fay")
    post = lambda **b: client.post("/visits", json={"companyId": doc["id"], **b}, headers=field["fay"])  # noqa: E731
    assert post(outcome="collected").json()["detail"][0]["loc"] == ["body", "amountCentavos"]
    assert post(outcome="promised", amountCentavos=100).json()["detail"][0]["loc"] == ["body", "amountCentavos"]
    assert post(outcome="not_in", receiptNo="OR-9").json()["detail"][0]["loc"] == ["body", "receiptNo"]
    assert post(outcome="collected", amountCentavos=100, visitedAt="2099-01-01T09:00:00").json()["detail"][0]["loc"] == ["body", "visitedAt"]
    # Changed to something else, a collection drops its amount and receipt.
    v = visit(client, field["fay"], doc, outcome="collected", amountCentavos=500, receiptNo="OR-2")
    changed = client.patch(f"/visits/{v['id']}", json={"outcome": "promised"}, headers=field["fay"]).json()
    assert (changed["outcome"], changed["amountCentavos"], changed["receiptNo"]) == ("promised", 0, None)
    # Agents don't delete visits; their lead may.
    assert client.delete(f"/visits/{v['id']}", headers=field["fay"]).status_code == 403
    assert client.delete(f"/visits/{v['id']}", headers=field["lia"]).status_code == 204


def upload(client, headers, rows, as_of="2026-08-31", dry_run=False):
    body = {"mapping": {"doctor": 0, "amount": 1, "note": 2}, "rows": rows, "dryRun": dry_run, "asOf": as_of}
    return client.post("/imports/balances", json=body, headers=headers)


def test_balances_upload_by_name_and_collections_bring_them_down(client, field):
    cruz = doctor(client, field, "Dr. Cruz", "fay")
    doctor(client, field, "Dr. Santos", "fay")
    doctor(client, field, "Dr. Santos ", "finn")  # the same name twice (ignoring spaces and case)
    r = upload(client, field["ana"], [["dr. cruz", "₱ 12,500.00", "Aug statement"], ["Dr. Lim", "100", ""], ["Dr. Santos", "5", ""], ["Dr. Cruz", "7", ""]])
    body = r.json()
    assert body["added"] == 1
    assert [p["row"] for p in body["problems"]] == [3, 4, 5]  # no such doctor, two of them, twice in the file
    assert "No customer called Dr. Lim" in body["problems"][0]["message"]
    # Only admins upload balances.
    assert upload(client, field["fay"], [["Dr. Cruz", "1", ""]]).status_code == 403

    # Paid on the cut-off day: already in the balance. Paid after it: comes off.
    visit(client, field["fay"], cruz, outcome="collected", amountCentavos=100000, receiptNo="OR-1", visitedAt="2026-08-31T15:00:00")
    visit(client, field["fay"], cruz, outcome="collected", amountCentavos=250000, receiptNo="OR-2", visitedAt="2026-09-02T10:00:00")
    owed = client.get(f"/field/doctors/{cruz['id']}", headers=field["fay"]).json()["balance"]
    assert owed == {"asOf": "2026-08-31", "balanceCentavos": 1250000, "collectedSinceCentavos": 250000, "owedCentavos": 1000000}
    listed = client.get("/field/doctors?owed=true", headers=field["fay"]).json()
    assert [d["name"] for d in listed["items"]] == ["Dr. Cruz"] and listed["owedCentavos"] == 1000000
    # Finn's doctors aren't Fay's to see.
    assert client.get(f"/field/doctors/{cruz['id']}", headers=field["finn"]).status_code == 404


def test_the_month_against_its_goals(client, field):
    cruz, lim = doctor(client, field, "Dr. Cruz", "fay"), doctor(client, field, "Dr. Lim", "fay")
    visit(client, field["fay"], cruz, outcome="collected", amountCentavos=300000, receiptNo="OR-1")
    visit(client, field["fay"], cruz, outcome="collected", amountCentavos=200000, receiptNo="OR-2", visitedAt=f"{MONTH}-20T10:00:00")
    visit(client, field["fay"], lim, outcome="not_in")
    visit(client, field["fay"], lim, outcome="promised", visitedAt="2026-08-30T10:00:00")  # last month
    assert client.patch(f"/companies/{lim['id']}", json={"phone": "0917 000 0000"}, headers=field["fay"]).status_code == 200

    goals = {"goals": [{"userId": field["ids"]["fay"], "doctorsVisited": 10, "doctorsUpdated": 4, "amountCentavos": 1000000, "collectionVisits": 5}]}
    assert client.put(f"/field/goals?month={MONTH}", json=goals, headers=field["fay"]).status_code == 403  # agents don't set goals
    assert client.put(f"/field/goals?month={MONTH}", json=goals, headers=field["ana"]).status_code == 200

    mine = client.get(f"/field/performance?month={MONTH}", headers=field["fay"]).json()
    assert [p["person"]["name"] for p in mine["people"]] == ["Fay"]  # an agent sees their own
    fay = mine["people"][0]
    # The phone change isn't dated in September here, so only count what's certain.
    assert fay["actual"]["doctorsVisited"] == 2 and fay["actual"]["collectionVisits"] == 2
    assert fay["actual"]["amountCentavos"] == 500000
    assert fay["goal"] == {"doctorsVisited": 10, "doctorsUpdated": 4, "amountCentavos": 1000000, "collectionVisits": 5}
    assert mine["canSetGoals"] is False

    # Her lead sees North's agents (not herself, not South); the admin sees everyone's.
    assert [p["person"]["name"] for p in client.get(f"/field/performance?month={MONTH}", headers=field["lia"]).json()["people"]] == ["Fay", "Finn"]
    assert [p["person"]["name"] for p in client.get(f"/field/performance?month={MONTH}", headers=field["ana"]).json()["people"]] == ["Fay", "Finn", "Sol"]
    assert client.get("/field/performance?month=2026-13", headers=field["fay"]).status_code == 422


def test_doctors_updated_counts_each_doctor_once_this_month(client, field):
    cruz, lim = doctor(client, field, "Dr. Cruz", "fay"), doctor(client, field, "Dr. Lim", "fay")
    for change in ({"phone": "1"}, {"phone": "2"}):
        client.patch(f"/companies/{cruz['id']}", json=change, headers=field["fay"])
    client.patch(f"/companies/{lim['id']}", json={"city": "Cebu"}, headers=field["fay"])
    now = client.get("/field/performance", headers=field["fay"]).json()
    assert now["month"] == now["thisMonth"]
    assert now["people"][0]["actual"]["doctorsUpdated"] == 2


def test_the_plan_tiers_zones_and_coverage(client, field):
    # The Rx playbook's plan: each doctor a tier (visits a month) and a zone; the month's coverage of the list.
    cruz, reyes, santos = (doctor(client, field, n, "fay") for n in ("Dr. Cruz", "Dr. Reyes", "Dr. Santos"))
    sols = doctor(client, field, "Dr. Lim", "sol")
    plan = client.put(f"/field/doctors/{cruz['id']}/plan", json={"tier": 1, "zone": "red"}, headers=field["fay"]).json()
    assert (plan["tier"], plan["zone"], plan["visitsNeeded"]) == (1, "red", 4) and plan["zoneSetAt"]
    client.put(f"/field/doctors/{reyes['id']}/plan", json={"tier": 3, "zone": "green"}, headers=field["fay"])
    # Someone else's doctor isn't hers to plan; a zone that isn't one is refused.
    assert client.put(f"/field/doctors/{sols['id']}/plan", json={"tier": 1}, headers=field["fay"]).status_code == 404
    assert client.put(f"/field/doctors/{santos['id']}/plan", json={"zone": "blue"}, headers=field["fay"]).status_code == 422
    # Clearing one leaves the other.
    cleared = client.put(f"/field/doctors/{reyes['id']}/plan", json={"zone": None}, headers=field["fay"]).json()
    assert (cleared["tier"], cleared["zone"]) == (3, None)

    visit(client, field["fay"], reyes)
    for day in (3, 10, 17, 24):
        visit(client, field["fay"], cruz, visitedAt=f"{MONTH}-{day:02d}T09:00:00")
    c = client.get("/field/coverage", params={"month": MONTH}, headers=field["fay"]).json()
    assert (c["doctors"], c["visited"], c["coveragePct"], c["goalPct"]) == (3, 2, 67, 80)
    tiers = {t["tier"]: t for t in c["tiers"]}
    assert (tiers[1]["doctors"], tiers[1]["onPlan"]) == (1, 1) and (tiers[3]["doctors"], tiers[3]["onPlan"]) == (1, 1)
    assert c["untiered"] == 1 and c["zones"] == {"red": 1, "yellow": 0, "green": 0, "none": 2}
    # Her lead's list is the team's.
    assert client.get("/field/coverage", params={"month": MONTH}, headers=field["lia"]).json()["doctors"] == 3

    by_plan = client.get("/field/doctors", params={"sort": "plan"}, headers=field["fay"]).json()["items"]
    assert [d["name"] for d in by_plan] == ["Dr. Cruz", "Dr. Reyes", "Dr. Santos"]
    reds = client.get("/field/doctors", params={"zone": "red"}, headers=field["fay"]).json()["items"]
    assert [d["name"] for d in reds] == ["Dr. Cruz"]
    unzoned = client.get("/field/doctors", params={"zone": "none", "tier": 3}, headers=field["fay"]).json()["items"]
    assert [d["name"] for d in unzoned] == ["Dr. Reyes"]


def test_a_call_logged_as_a_visit(client, field):
    # The Rx playbook's call: products detailed, and the Patient Care Group step; enrolling marks the doctor.
    cruz = doctor(client, field, "Dr. Cruz", "fay")
    v = visit(client, field["fay"], cruz, outcome="detailed", careGroup="enrolled")
    assert (v["outcome"], v["careGroup"], v["amountCentavos"]) == ("detailed", "enrolled", 0)
    row = next(d for d in client.get("/field/doctors", headers=field["fay"]).json()["items"] if d["id"] == cruz["id"])
    assert row["careGroupAt"]
    assert client.post("/visits", json={"companyId": cruz["id"], "outcome": "detailed", "careGroup": "maybe", "location": HERE}, headers=field["fay"]).status_code == 422
