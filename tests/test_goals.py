"""Focus goals and each person's home dashboard."""

from datetime import date

import pytest

from app.goals import BY_KEY, Month, SalesMonth, goal_results, judge, measure_sales
from app.retention import CustomerFacts, Rules
from tests.conftest import customer_id, post_quote, product_ids

SEP_18 = Month(date(2026, 9, 1), date(2026, 9, 18), 30)


@pytest.mark.parametrize(
    ("goal", "value", "target", "status", "expected"),
    [
        ("quotes", 30, 30, "met", None),
        ("quotes", 18, 30, "on_pace", 18),  # 18th of a 30-day month: 18 is on pace
        ("quotes", 12, 30, "behind", 18),
        ("retention", 7000, 8000, "below", None),  # a rate has no pace
        ("approval_days", 1.5, 2, "met", None),  # lower is better
        ("approval_days", 3.2, 2, "over", None),
        ("retention", None, 8000, "no_data", None),
    ],
)
def test_judging_a_goal(goal, value, target, status, expected):
    result = judge(BY_KEY[goal], value, target, SEP_18)
    assert (result["status"], result["expected"]) == (status, expected)


def test_a_teams_per_rep_target_scales_with_the_team():
    targets = {"quotes": 30, "retention": 8000, "quoted_value": 1, "follow_ups_on_time": 1, "new_customers": 1, "activities": 1}
    by_key = lambda values: {r["key"]: r for r in goal_results(values, targets, SEP_18, reps=3)}  # noqa: E731
    three = by_key({"quotes": 54, "retention": 9000})
    # Three reps at 30 each: 90 for the month, so 54 is expected by the 18th.
    assert (three["quotes"]["target"], three["quotes"]["expected"], three["quotes"]["status"]) == (90, 54, "on_pace")
    assert by_key({"quotes": 50})["quotes"]["status"] == "behind"
    assert three["retention"]["target"] == 8000  # a rate isn't multiplied


def test_measuring_a_reps_month():
    ana, ben = "ana", "ben"
    data = SalesMonth(
        customers=[
            CustomerFacts("c1", "C1", "b2c", "general", "active", ana, "Ana", (date(2026, 5, 1), date(2026, 8, 1)), (1, 1),
                          created_on=date(2026, 9, 3), created_by=ana),
            CustomerFacts("c2", "C2", "b2c", "general", "active", ben, "Ben", (), (), created_on=date(2026, 8, 30), created_by=ben),
        ],
        quotes=[{"createdById": ana, "totalCentavos": 150_00}, {"createdById": ana, "totalCentavos": 50_00}, {"createdById": ben, "totalCentavos": 1}],
        activities=[{"byId": ana, "kind": "call"}, {"byId": ana, "kind": "note"}, {"byId": ana, "kind": "visit"}, {"byId": ben, "kind": "call"}],
        follow_ups=[
            {"_id": "f1", "assigneeId": ana, "dueOn": "2026-09-10", "status": "done"},  # done on time
            {"_id": "f2", "assigneeId": ana, "dueOn": "2026-09-12", "status": "done"},  # done late
            {"_id": "f3", "assigneeId": ana, "dueOn": "2026-09-15", "status": "open"},  # overdue
            {"_id": "f4", "assigneeId": ana, "dueOn": "2026-09-18", "status": "open"},  # due today: not late yet
        ],
        done_on={"f1": "2026-09-09", "f2": "2026-09-14"},
    )
    values = measure_sales(data, {ana}, {"b2c": Rules(45, 90)}, SEP_18)
    assert values == {
        "retention": 10_000,  # quoted in May (previous window) and August (this one)
        "quotes": 2,
        "quoted_value": 200_00,
        "follow_ups_on_time": 3333,  # 1 of 3 due so far
        "new_customers": 1,
        "activities": 2,  # notes aren't calls, visits or messages
    }
    everyone = measure_sales(data, None, {"b2c": Rules(45, 90)}, SEP_18)
    assert (everyone["quotes"], everyone["activities"], everyone["new_customers"]) == (3, 3, 1)


# --- the dashboard API -------------------------------------------------------------------


def dashboard(client, headers):
    r = client.get("/me/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def goal(entry: dict, key: str) -> dict:
    return next(g for g in entry["goals"] if g["key"] == key)


def test_a_rep_sees_their_own_goals_in_each_division(client, as_):
    ana = as_("ana")
    maria = customer_id(client, ana, "b2c", "Maria Lopez")
    line = [{"productId": product_ids(client, ana, "b2c")["MET-500"], "quantity": 2}]
    assert post_quote(client, ana, "b2c", maria, {"priceType": "patient", "lines": line}).status_code == 201

    body = dashboard(client, ana)
    assert [m["name"] for m in body["mine"]] == ["B2C", "B&B"]
    b2c = body["mine"][0]
    assert goal(b2c, "quotes")["value"] == 1 and goal(b2c, "quoted_value")["value"] == 144000
    assert goal(b2c, "quotes")["target"] == 30 and len(b2c["trend"]) == 12
    assert body["teams"] == [] and body["divisions"] == [] and body["finance"] is None and body["admin"] is None


def test_a_team_lead_sees_each_person_on_the_team(client, as_):
    body = dashboard(client, as_("paolo"))
    [team] = body["teams"]
    assert team["name"] == "B&B"
    # Everyone who can add records in B&B / MD Telesales: the reps, the lead, the division head.
    assert [r["name"] for r in team["rows"]] == ["Ana Reyes", "Lorna Bautista", "Paolo Mendoza"]
    assert goal(team, "quotes")["target"] == 30 * 3  # per-rep target times the team


def test_an_executive_compares_divisions(client, as_):
    body = dashboard(client, as_("ramon"))
    assert body["mine"] == []  # views everything, sells nothing
    assert [d["name"] for d in body["divisions"]] == ["B2C", "STC", "URO", "B&B", "B2B", "HOS", "BID"]
    assert all("rows" not in d for d in body["divisions"])
    assert body["finance"] is not None  # executives can view Finance


def test_finance_inventory_and_admin_get_their_own_desks(client, as_):
    joy = dashboard(client, as_("joy"))
    assert joy["mine"] == [] and joy["inventory"] is None
    assert joy["finance"]["counts"] == {"approvals": 0, "letters": 0, "payments": 0}
    assert [g["key"] for g in joy["finance"]["goals"]] == ["approval_days", "letter_days"]

    iris = dashboard(client, as_("iris"))
    assert iris["inventory"]["missingCount"] == 1 and iris["inventory"]["missing"][0]["missing"] == ["Government Price"]
    assert goal(iris["inventory"], "fully_priced")["value"] == 8000  # 4 of 5 products

    carmen = dashboard(client, as_("carmen"))
    assert carmen["admin"]["noPrices"] == ["URO", "B&B"] and carmen["admin"]["noRoleCount"] == 0
    assert carmen["mine"] == [] and carmen["finance"] is None


def test_admins_set_targets(client, as_):
    carmen = as_("carmen")
    assert client.get("/admin/goals", headers=as_("ana")).status_code == 403
    body = client.get("/admin/goals", headers=carmen).json()
    assert body["targets"]["b2c"]["quotes"] == 30 and {d["area"] for d in body["divisions"]} == {"sales", "finance", "inventory"}

    r = client.put("/admin/goals", json={"targets": {"b2c": {"quotes": 45, "retention": 8500}, "finance": {"approval_days": 1}}}, headers=carmen)
    assert r.status_code == 200 and r.json()["targets"]["b2c"]["quotes"] == 45
    assert goal(dashboard(client, as_("ana"))["mine"][0], "quotes")["target"] == 45

    bad = [
        {"b2c": {"approval_days": 1}},  # a Finance goal on a sales division
        {"finance": {"quotes": 3}},
        {"b2c": {"retention": 12_000}},  # over 100%
        {"hr": {"quotes": 3}},
    ]
    for targets in bad:
        assert client.put("/admin/goals", json={"targets": targets}, headers=carmen).status_code == 422


def test_a_company_chooses_which_goals_it_tracks(client, as_):
    """Orbit can work out every goal; a company decides which it cares about."""
    carmen, lorna = as_("carmen"), as_("lorna")
    catalogue = client.get("/admin/goals", headers=carmen).json()["goals"]
    assert all(g["isTracked"] for g in catalogue), "everything is tracked until someone says otherwise"

    keep = [g["key"] for g in catalogue if g["key"] != "activities"]
    r = client.put("/admin/goals/tracked", json={"keys": keep}, headers=carmen)
    assert r.status_code == 200
    assert {g["key"]: g["isTracked"] for g in r.json()["goals"]}["activities"] is False

    # the dashboards stop reporting it altogether
    home = dashboard(client, lorna)
    reported = {g["key"] for entry in home["mine"] for g in entry["goals"]}
    assert "activities" not in reported and "quotes" in reported
    assert "activities" not in {g["key"] for g in home["goals"] if g["isTracked"]}

    # switching it back on brings it and its target back untouched
    back = client.put("/admin/goals/tracked", json={"keys": [g["key"] for g in catalogue]}, headers=carmen)
    assert {g["key"]: g["isTracked"] for g in back.json()["goals"]}["activities"] is True
    assert "activities" in {g["key"] for entry in dashboard(client, lorna)["mine"] for g in entry["goals"]}


def test_a_goal_that_does_not_exist_is_refused(client, as_):
    assert client.put("/admin/goals/tracked", json={"keys": ["moon_landings"]}, headers=as_("carmen")).status_code == 422


def test_only_an_admin_changes_which_goals_are_tracked(client, as_):
    assert client.put("/admin/goals/tracked", json={"keys": []}, headers=as_("lorna")).status_code == 403
