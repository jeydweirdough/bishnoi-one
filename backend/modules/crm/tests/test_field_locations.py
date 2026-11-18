"""Field locations: a clinic's pin, where each visit was logged, and agents'
trails (packed, joined into the day's distance, only in work hours)."""

from datetime import UTC, datetime, timedelta

import pytest

from modules.crm.config import Settings
from modules.crm.routers import field as field_router
from modules.crm.trail import Point, decode, encode
from modules.crm.tests.test_field import doctor, field  # noqa: F401 (field is a fixture)

CLINIC = (14.55432, 121.02447)  # Makati
NEAR = (14.55470, 121.02480)  # ~55 m away
FAR = (14.56500, 121.02447)  # ~1.2 km away


@pytest.fixture
def all_day(monkeypatch):
    """Work hours around the clock, so these tests pass whenever they run."""
    monkeypatch.setattr(field_router, "WORK_HOURS", (0, 24))


def pin(client, headers, doc, where=CLINIC, accuracy=10):
    return client.put(f"/field/doctors/{doc['id']}/location", json={"latitude": where[0], "longitude": where[1], "accuracyM": accuracy}, headers=headers)


def visit_at(client, headers, doc, where, accuracy=15):
    body = {"companyId": doc["id"], "outcome": "not_in", "location": {"latitude": where[0], "longitude": where[1], "accuracyM": accuracy}}
    r = client.post("/visits", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_packing_keeps_every_point_exactly():
    start = datetime(2026, 9, 25, 1, 0, tzinfo=UTC)
    points = [Point(14.55432 + i * 0.0009, 121.02447 - i * 0.0004, 12 + i, start + timedelta(seconds=60 * i)) for i in range(15)]
    packed = encode(points, start)
    assert len(packed) < 150  # about 7 characters a point, against ~95 as JSON
    assert decode(packed, start) == [Point(round(p.lat, 5), round(p.lng, 5), p.accuracy_m, p.at) for p in points]


def test_a_visit_is_told_at_the_clinic_or_elsewhere(client, field):
    doc = doctor(client, field, "Dr. Cruz", "fay")
    assert "accuracyM" in str(pin(client, field["fay"], doc, accuracy=400).json())  # not sure enough to pin
    assert pin(client, field["fay"], doc).json()["pin"]["latitude"] == CLINIC[0]
    near, far = visit_at(client, field["fay"], doc, NEAR), visit_at(client, field["fay"], doc, FAR)
    assert near["atClinic"] is True and near["distanceM"] < 100
    assert far["atClinic"] is False and 1100 < far["distanceM"] < 1300
    # An agent can't log a visit without a location...
    bare = client.post("/visits", json={"companyId": doc["id"], "outcome": "not_in"}, headers=field["fay"])
    assert bare.status_code == 422 and bare.json()["detail"][0]["loc"] == ["body", "location"]
    # ...their lead, logging one for them, can: then nothing is claimed either way.
    plain = client.post("/visits", json={"companyId": doc["id"], "outcome": "not_in"}, headers=field["lia"]).json()
    assert (plain["location"], plain["atClinic"]) == (None, None)
    # Pinning isn't updating the doctor's details: it doesn't count toward the goal.
    assert client.get("/field/performance", headers=field["fay"]).json()["people"][0]["actual"]["doctorsUpdated"] == 0
    # Agents don't take pins away; their lead does.
    assert client.delete(f"/field/doctors/{doc['id']}/location", headers=field["fay"]).status_code == 403
    assert client.delete(f"/field/doctors/{doc['id']}/location", headers=field["lia"]).status_code == 204


def trail(start: datetime, n: int, step_s=60, accuracy=10):
    return [
        {"latitude": CLINIC[0] + i * 0.0009, "longitude": CLINIC[1], "accuracyM": accuracy, "at": (start + timedelta(seconds=step_s * i)).isoformat()}
        for i in range(n)
    ]


def test_trails_are_packed_and_joined_into_the_day(client, field, all_day):
    start = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=40)
    first = trail(start, 10) + [{**trail(start + timedelta(seconds=30), 1)[0], "accuracyM": 900}]  # a wild reading: kept, weak
    r = client.post("/field/trail", json={"points": first}, headers=field["fay"]).json()
    assert (r["received"], r["kept"], r["weak"]) == (11, 11, 1)
    second = [{**p, "latitude": p["latitude"] + 0.009} for p in trail(start + timedelta(minutes=15), 5)]
    client.post("/field/trail", json={"points": second}, headers=field["fay"])
    route = client.get("/field/routes", headers=field["fay"]).json()
    assert len(route["points"]) == 16 and sum(p["weak"] for p in route["points"]) == 1
    # ~9 x 100 m, then on from there (~0 m jump), then 4 x 100 m: about 1.3 km.
    assert 1200 < route["summary"]["distanceM"] < 1500
    days = client.get("/field/routes/days", headers=field["fay"]).json()["days"]
    assert [d["day"] for d in days] == [route["day"]]


def test_old_and_out_of_hours_points_are_not_kept(client, field, monkeypatch):
    monkeypatch.setattr(field_router, "WORK_HOURS", (0, 0))  # no work hours at all
    now = datetime.now(UTC).replace(microsecond=0)
    r = client.post("/field/trail", json={"points": trail(now - timedelta(minutes=5), 3)}, headers=field["fay"]).json()
    assert r["kept"] == 0
    monkeypatch.setattr(field_router, "WORK_HOURS", (0, 24))
    r = client.post("/field/trail", json={"points": trail(now - timedelta(days=8), 3)}, headers=field["fay"]).json()
    assert r["kept"] == 0  # more than 7 days old
    r = client.post("/field/trail", json={"points": trail(now + timedelta(hours=1), 3)}, headers=field["fay"]).json()
    assert r["kept"] == 0  # not yet
    settings = Settings(_env_file=None, org_timezone="Asia/Manila")
    monkeypatch.setattr(field_router, "WORK_HOURS", (6, 20))
    assert field_router.in_work_hours(datetime(2026, 9, 25, 1, 0, tzinfo=UTC), settings)  # 9:00 in Manila
    assert not field_router.in_work_hours(datetime(2026, 9, 25, 13, 0, tzinfo=UTC), settings)  # 21:00 in Manila


def test_who_sees_whose_route(client, field, all_day):
    start = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=20)
    client.post("/field/trail", json={"points": trail(start, 4)}, headers=field["fay"])
    fay, sol = field["ids"]["fay"], field["ids"]["sol"]
    assert client.get(f"/field/routes?person={fay}", headers=field["finn"]).status_code == 403  # agents: their own only
    assert len(client.get(f"/field/routes?person={fay}", headers=field["lia"]).json()["points"]) == 4  # her lead
    assert client.get(f"/field/routes?person={sol}", headers=field["lia"]).status_code == 404  # not her team
    assert len(client.get(f"/field/routes?person={fay}", headers=field["ana"]).json()["points"]) == 4  # the admin


# --- Step 4H: the phone's offline queue -----------------------------------------------------------


def test_points_kept_offline_for_days_still_count(client, field, all_day):
    """A phone offline for three days sends its points late, and today's before them: both days are drawn right."""
    now = datetime.now(UTC).replace(microsecond=0)
    today = trail(now - timedelta(minutes=30), 5)
    old = trail(now - timedelta(days=3), 5)
    assert client.post("/field/trail", json={"points": today}, headers=field["fay"]).json()["kept"] == 5
    assert client.post("/field/trail", json={"points": old}, headers=field["fay"]).json()["kept"] == 5
    assert len(client.get("/field/routes", headers=field["fay"]).json()["points"]) == 5
    old_day = field_router.local_day(now - timedelta(days=3), Settings(_env_file=None))
    route = client.get(f"/field/routes?day={old_day}", headers=field["fay"]).json()
    assert len(route["points"]) == 5 and 350 < route["summary"]["distanceM"] < 450
    assert old_day in {d["day"] for d in client.get(f"/field/routes/days?month={old_day[:7]}", headers=field["fay"]).json()["days"]}


def test_a_batch_sent_twice_is_kept_once(client, field, all_day):
    start = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=30)
    points = [{**p, "clientId": f"pt-{i:06d}-abcdef"} for i, p in enumerate(trail(start, 6))]
    assert client.post("/field/trail", json={"points": points[:4]}, headers=field["fay"]).json()["kept"] == 4
    # The answer was lost: the phone sends them again, with the rest.
    r = client.post("/field/trail", json={"points": points}, headers=field["fay"]).json()
    assert (r["received"], r["kept"]) == (6, 2)
    route = client.get("/field/routes", headers=field["fay"]).json()
    assert len(route["points"]) == 6 and route["summary"]["points"] == 6
    assert 450 < route["summary"]["distanceM"] < 550  # 5 x 100 m, not counted twice


def test_weak_points_are_kept_marked_and_left_out_of_the_distance(client, field, all_day):
    start = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=30)
    points = trail(start, 3)
    # A weak reading 5 km off between the second and third: drawn as weak, not walked.
    wild = {"latitude": CLINIC[0] + 0.045, "longitude": CLINIC[1], "accuracyM": 350, "at": (start + timedelta(seconds=90)).isoformat()}
    late = {**trail(start + timedelta(minutes=10), 1)[0], "accuracyM": 800}
    r = client.post("/field/trail", json={"points": points + [wild, late]}, headers=field["fay"]).json()
    assert (r["kept"], r["weak"]) == (5, 2)
    route = client.get("/field/routes", headers=field["fay"]).json()
    assert [p["weak"] for p in route["points"]] == [False, False, True, False, True]
    assert route["points"][2]["accuracyM"] == 350 and route["weakAccuracyM"] == 200
    summary = route["summary"]
    assert 150 < summary["distanceM"] < 250 and summary["points"] == 5
    # The day ends at its last sure point, not the weak one after it.
    assert summary["lastAt"].startswith(points[-1]["at"][:19])


def test_a_visit_logged_offline_is_kept_once_with_the_phones_time(client, field):
    doc = doctor(client, field, "Dr. Reyes", "fay")
    logged = (datetime.now(UTC) - timedelta(days=2)).replace(microsecond=0)
    body = {"companyId": doc["id"], "outcome": "not_in", "visitedAt": logged.isoformat(), "clientId": "visit-0001-phone",
            "location": {"latitude": CLINIC[0], "longitude": CLINIC[1], "accuracyM": 20}}
    first = client.post("/visits", json=body, headers=field["fay"])
    assert first.status_code == 201, first.text
    assert first.json()["visitedAt"].startswith(logged.isoformat()[:19])
    again = client.post("/visits", json=body, headers=field["fay"])
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert client.get(f"/visits?company={doc['id']}", headers=field["fay"]).json()["total"] == 1
    # Another phone's id is another visit; the future is refused; a bad id is refused.
    assert client.post("/visits", json={**body, "clientId": "visit-0002-phone"}, headers=field["fay"]).status_code == 201
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    assert client.post("/visits", json={**body, "clientId": "visit-0003-phone", "visitedAt": future}, headers=field["fay"]).status_code == 422
    assert client.post("/visits", json={**body, "clientId": "no spaces!"}, headers=field["fay"]).status_code == 422
