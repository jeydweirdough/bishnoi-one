"""A field agent's week, planned by zone, and their coach's review (app/routers/field_plan.py)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.test_field import HERE, doctor, field  # noqa: F401 (field is a fixture)

TODAY = datetime.now(ZoneInfo("Asia/Manila")).date()
# Next week, so every day of it is still to come.
MONDAY = TODAY - timedelta(days=TODAY.weekday()) + timedelta(days=7)
DAYS = [(MONDAY + timedelta(days=i)).isoformat() for i in range(5)]


def plan(client, headers, **params):
    return client.get("/field/plan", params={"week": MONDAY.isoformat(), **params}, headers=headers).json()


def test_a_week_by_zone_sent_to_the_coach(client, field):
    cruz, reyes, santos = (doctor(client, field, n, "fay") for n in ("Dr. Cruz", "Dr. Reyes", "Dr. Santos"))
    client.put(f"/field/doctors/{cruz['id']}/plan", json={"tier": 1, "zone": "red"}, headers=field["fay"])
    client.put(f"/field/doctors/{reyes['id']}/plan", json={"tier": 2, "zone": "yellow"}, headers=field["fay"])
    client.put(f"/field/doctors/{santos['id']}/plan", json={"zone": "green"}, headers=field["fay"])

    # By hand: the part of the day follows the zone.
    stop = client.post("/field/plan/stops", json={"companyId": santos["id"], "day": DAYS[0]}, headers=field["fay"]).json()
    assert stop["slot"] == "afternoon" and stop["visited"] is False
    assert client.post("/field/plan/stops", json={"companyId": santos["id"], "day": DAYS[0]}, headers=field["fay"]).status_code == 422
    saturday = (MONDAY + timedelta(days=5)).isoformat()
    assert client.post("/field/plan/stops", json={"companyId": cruz["id"], "day": saturday}, headers=field["fay"]).status_code == 422
    sols = doctor(client, field, "Dr. Lim", "sol")
    assert client.post("/field/plan/stops", json={"companyId": sols["id"], "day": DAYS[1]}, headers=field["fay"]).status_code == 422

    # Filled from the zones: Cruz (tier 1) 4 times, Reyes (tier 2) twice, Santos once already.
    assert client.post("/field/plan/fill", params={"week": MONDAY.isoformat()}, headers=field["fay"]).json()["added"] == 6
    week = plan(client, field["fay"])
    names = [s["doctor"]["name"] for d in week["days"] for s in d["stops"]]
    assert names.count("Dr. Cruz") == 4 and names.count("Dr. Reyes") == 2 and names.count("Dr. Santos") == 1
    monday = week["days"][0]["stops"]
    assert [s["slot"] for s in monday] == sorted((s["slot"] for s in monday), key=["morning", "midday", "afternoon"].index)
    assert week["can"] == {"plan": True, "review": False}
    # Filling again adds nothing.
    assert client.post("/field/plan/fill", params={"week": MONDAY.isoformat()}, headers=field["fay"]).json()["added"] == 0

    # To the coach: she can't review a week not sent, then reviews it.
    lia_view = {"person": field["ids"]["fay"]}
    assert plan(client, field["lia"], **lia_view)["can"] == {"plan": False, "review": True}
    sent = client.post("/field/plan/send", params={"week": MONDAY.isoformat()}, headers=field["fay"])
    assert sent.status_code == 200
    # The coach takes one off; Sol (another team's agent) can't see the week.
    first = plan(client, field["lia"], **lia_view)["days"][0]["stops"][0]
    assert client.delete(f"/field/plan/stops/{first['id']}", headers=field["lia"]).status_code == 204
    assert client.get("/field/plan", params={"person": field["ids"]["fay"]}, headers=field["sol"]).status_code == 403
    r = client.post("/field/plan/review", json={"person": field["ids"]["fay"], "week": MONDAY.isoformat(), "note": "Fewer greens on Monday."}, headers=field["lia"])
    assert r.status_code == 200
    status = plan(client, field["fay"])["status"]
    assert status["reviewedBy"]["name"] == "Lia" and status["note"] == "Fewer greens on Monday." and status["changedAt"] is None
    # A change after that shows.
    extra = client.post("/field/plan/stops", json={"companyId": santos["id"], "day": DAYS[4]}, headers=field["fay"])
    assert extra.status_code == 201 and plan(client, field["fay"])["status"]["changedAt"]


def test_a_visit_ticks_off_its_stop(client, field):
    cruz = doctor(client, field, "Dr. Cruz", "fay")
    today = TODAY if TODAY.weekday() < 5 else None
    if today is None:
        return  # a weekend: nothing to plan today
    client.post("/field/plan/stops", json={"companyId": cruz["id"], "day": today.isoformat()}, headers=field["fay"])
    client.post("/visits", json={"companyId": cruz["id"], "outcome": "other", "location": HERE}, headers=field["fay"])
    week = client.get("/field/plan", headers=field["fay"]).json()
    stops = [s for d in week["days"] for s in d["stops"]]
    assert [s["visited"] for s in stops] == [True]
