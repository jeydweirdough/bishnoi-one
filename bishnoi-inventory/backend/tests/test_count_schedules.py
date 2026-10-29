"""Scheduled cycle counts (feature plan step 14b, app/count_schedules.py): due from their day, started in one
click, approving the count sets the next day; count accuracy per warehouse."""

from datetime import date, timedelta

from tests.conftest import receive


def test_a_schedule_comes_due_is_counted_and_comes_round_again(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 20}])
    later = ana.post("/inventory/count-schedules", {"name": "Gloves weekly", "warehouseId": world["mnl"], "everyDays": 7, "nextOn": (date.today() + timedelta(days=3)).isoformat()})
    assert later["due"] is False
    s = ana.post("/inventory/count-schedules", {"name": "Manila monthly", "warehouseId": world["mnl"], "everyDays": 30})
    listed = ana.get("/inventory/count-schedules")
    assert listed["due"] == 1 and listed["items"][0]["id"] == s["id"]

    c = ana.post(f"/inventory/count-schedules/{s['id']}/start")
    assert ana.c.post(f"/inventory/count-schedules/{s['id']}/start", headers=ana.h).status_code == 409  # one open count at a time
    count = ana.get(f"/inventory/counts/{c['id']}")
    assert count["scheduleId"] == s["id"] and count["header"]["scheduledOn"] == s["nextOn"]
    assert ana.get("/inventory/count-schedules")["items"][0]["openCount"]["number"] == c["number"]

    line = count["lines"][0]
    ana.put(f"/inventory/counts/{c['id']}/lines", {"lines": [{"lineId": line["id"], "counted": line["expected"] - 2}]})
    ana.post(f"/inventory/counts/{c['id']}/submit")
    ana.post(f"/inventory/counts/{c['id']}/approve")
    after = next(x for x in ana.get("/inventory/count-schedules")["items"] if x["id"] == s["id"])
    assert after["due"] is False and after["openCount"] is None
    assert after["nextOn"] == (date.fromisoformat(after["lastCountedOn"]) + timedelta(days=30)).isoformat()

    report = ana.get("/inventory/reports/count-accuracy")
    row = report["rows"][0]
    assert (row["counts"], row["scheduled"], row["lines"], row["matched"], row["unitsOff"]) == (1, 1, 1, 0, 2)
    assert next(c for c in report["columns"] if c["key"] == "accuracy")["ratio"] == ["matched", "lines"]


def test_only_approvers_set_schedules(client, people, world):
    from tests.conftest import Api

    sal = Api(client, people["sal"])
    r = sal.c.post("/inventory/count-schedules", headers=sal.h, json={"name": "X", "warehouseId": world["mnl"], "everyDays": 7})
    assert r.status_code == 403
