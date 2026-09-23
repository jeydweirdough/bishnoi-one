"""Customer retention: the arithmetic on its own, then who sees what."""

import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.retention import AT_RISK, HEALTHY, LOST, NO_QUOTES, CustomerFacts, Rules, health, month_ends, window_on
from app.scope import Scope
from app.store.query import Query
from app.store.records import Create
from app.tenancy import FIRST_ORG_ID, set_company

TODAY = date(2026, 9, 18)
RULES = {"b2c": Rules(45, 90), "hos": Rules(20, 30)}


def facts(name: str, *days_ago: int, division: str = "b2c", status: str = "active") -> CustomerFacts:
    days = tuple(sorted(TODAY - timedelta(days=d) for d in days_ago))
    return CustomerFacts(name, name, division, "general", status, "ana", "Ana", days, tuple(100 for _ in days))


@pytest.mark.parametrize(
    ("days_ago", "expected"),
    [((10,), HEALTHY), ((45,), HEALTHY), ((46,), AT_RISK), ((90,), AT_RISK), ((91,), LOST), ((), NO_QUOTES)],
)
def test_health_follows_the_divisions_days(days_ago, expected):
    assert health(facts("x", *days_ago), RULES["b2c"], TODAY) == expected


def test_a_customer_marked_inactive_is_lost():
    assert health(facts("x", 5, status="inactive"), RULES["b2c"], TODAY) == LOST


def test_retention_compares_the_last_window_with_the_one_before():
    customers = [
        facts("kept", 100, 10),  # quoted in both windows: retained
        facts("gone", 120),  # only in the previous one: lost
        facts("new", 30),  # first quote in this window: new, not in the base
        facts("old", 200),  # before both windows
    ]
    w = window_on(customers, RULES, TODAY)
    assert (w.base, w.retained, w.lost, w.new, w.rate) == (2, 1, 1, 1, 0.5)


def test_each_division_uses_its_own_window():
    # HOS buys every 30 days: quotes 40 and 10 days ago are "retained" there, but
    # in B2C's 90-day windows the same dates are just two quotes in one window.
    assert window_on([facts("h", 40, 10, division="hos")], RULES, TODAY).rate == 1.0
    assert window_on([facts("b", 40, 10)], RULES, TODAY).base == 0


def test_no_base_means_no_rate():
    assert window_on([facts("new", 5)], RULES, TODAY).rate is None


def test_the_trend_is_twelve_month_ends_up_to_today():
    ends = month_ends(TODAY)
    assert len(ends) == 12 and ends[-1] == TODAY and ends[0] == date(2025, 10, 31) and ends[-2] == date(2026, 8, 31)


# --- the API -------------------------------------------------------------------------


def all_customers(records) -> dict[str, dict]:
    everything = frozenset(Scope(d, s) for d, s in [(k, t) for k in ("b2c", "stc", "uro", "bnb", "b2b", "hos") for t in ("general", "md-telesales", "nbd", "crr", "hospital", "telesales")])
    return {c["name"]: c for c in records.for_org(FIRST_ORG_ID).find(Query("customer", everything, limit=500))}


def quoted(records, customer: dict, days_ago: int, rejected: bool = False, total: int = 10000) -> None:
    at = (datetime.now(UTC) - timedelta(days=days_ago, hours=1)).isoformat(timespec="seconds").replace("+00:00", "Z")
    records.for_org(FIRST_ORG_ID).commit(
        [
            Create(
                {
                    "_id": str(uuid.uuid4()),
                    "_type": "quote",
                    **Scope.of(customer).stamp(),
                    "customerId": customer["_id"],
                    "createdAt": at,
                    "approvalStatus": "rejected" if rejected else "none",
                    "letterStatus": "none",
                    "totalCentavos": total,
                }
            )
        ]
    )


def test_reps_see_their_own_customers(client, as_, records):
    c = all_customers(records)
    quoted(records, c["Maria Lopez"], 60)  # at risk
    quoted(records, c["Jose Ramos"], 10)  # healthy
    quoted(records, c["Dr. Cora Aquino"], 60)  # Ben's, not Ana's
    body = client.get("/retention?division=b2c", headers=as_("ana")).json()
    assert body["canSeeTeam"] is False and body["reps"] == []
    s = body["summary"]
    assert (s["customers"], s["healthy"], s["atRisk"]) == (2, 1, 1)
    assert [(w["name"], w["health"], w["daysSince"]) for w in body["watch"]] == [("Maria Lopez", "at_risk", 60)]
    watch = body["watch"][0]
    assert watch["canWinBack"] and watch["followUp"]["title"] == "Check if the reorder went through"


def test_team_figures_need_reports(client, as_, records):
    c = all_customers(records)
    quoted(records, c["Dr. Alma Dizon"], 120)
    quoted(records, c["Dr. Alma Dizon"], 20)  # retained
    quoted(records, c["Dr. Victor Salcedo"], 100)  # lost
    quoted(records, c["Dr. Irene Galang"], 30)  # new
    quoted(records, c["Sta. Lucia Drugstore"], 10, rejected=True)  # doesn't count

    assert client.get("/retention?division=bnb&view=team", headers=as_("ana")).status_code == 403
    body = client.get("/retention?division=bnb&view=team", headers=as_("paolo")).json()
    s = body["summary"]
    assert (s["base"], s["retained"], s["lost"], s["new"], s["rate"]) == (2, 1, 1, 1, 0.5)
    assert s["noQuotes"] == 1  # the rejected quote isn't buying
    assert [(r["name"], r["customers"]) for r in body["reps"]] == [("Ana Reyes", 2), ("Paolo Mendoza", 2)]
    assert body["trend"][-1]["rate"] == 0.5 and len(body["trend"]) == 12

    # A division head sees every team in the division.
    lorna = client.get("/retention?division=bnb&view=team", headers=as_("lorna")).json()
    assert [r["name"] for r in lorna["reps"]] == ["Ana Reyes", "Lorna Bautista", "Paolo Mendoza"]
    only_general = client.get("/retention?division=bnb&view=team&team=general", headers=as_("lorna")).json()
    assert [r["name"] for r in only_general["reps"]] == ["Lorna Bautista"]


def test_the_export_is_a_spreadsheet_safe_csv(client, as_, records):
    paolo = as_("paolo")
    r = client.post("/sales/customers", json={"division": "bnb", "team": "md-telesales", "name": "=1+1 Pharmacy", "kind": "pharmacy"}, headers=paolo)
    assert r.status_code == 201
    quoted(records, all_customers(records)["Dr. Irene Galang"], 5, total=123456)

    r = client.get("/retention/export?division=bnb&view=team", headers=paolo)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "retention-bnb-team-" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    # The division is a column now: one export can hold more than one.
    assert rows[0][:6] == ["Customer", "Division", "Team", "Owner", "Status", "Health"]
    by_name = {row[0]: row for row in rows[1:]}
    assert "'=1+1 Pharmacy" in by_name  # not run as a formula
    irene = by_name["Dr. Irene Galang"]
    assert irene[1] == "B&B"
    assert (irene[5], irene[7], irene[8], irene[9]) == ("Healthy", "5", "1", "1234.56") and irene[6]


def test_home_lists_my_at_risk_customers_everywhere(client, as_, records):
    c = all_customers(records)
    quoted(records, c["Maria Lopez"], 60)  # B2C
    quoted(records, c["Dr. Alma Dizon"], 50)  # B&B
    quoted(records, c["Dr. Victor Salcedo"], 100)  # lost, counted but not listed
    body = client.get("/me/at-risk", headers=as_("ana")).json()
    assert [(i["name"], i["moduleName"], i["daysSince"]) for i in body["items"]] == [("Maria Lopez", "B2C", 60), ("Dr. Alma Dizon", "B&B", 50)]
    assert body["recentlyLost"] == 1


def test_divisions_side_by_side(client, as_):
    assert [d["code"] for d in client.get("/retention/divisions", headers=as_("ramon")).json()["divisions"]] == [
        "b2c", "stc", "uro", "bnb", "b2b", "hos", "bid"
    ]
    assert [d["code"] for d in client.get("/retention/divisions", headers=as_("lorna")).json()["divisions"]] == ["bnb"]
    assert client.get("/retention/divisions", headers=as_("ana")).status_code == 403


def test_admins_set_each_divisions_thresholds(client, as_, records):
    carmen = as_("carmen")
    assert client.get("/admin/retention", headers=as_("ana")).status_code == 403
    body = client.get("/admin/retention", headers=carmen).json()
    assert {(d["code"], d["atRiskDays"], d["lostDays"]) for d in body["divisions"]} == {
        (k, 45, 90) for k in ("b2c", "stc", "uro", "bnb", "b2b", "hos", "bid")
    }

    quoted(records, all_customers(records)["Maria Lopez"], 40)
    health_of_maria = lambda: client.get("/retention?division=b2c", headers=as_("ana")).json()["summary"]["atRisk"]  # noqa: E731
    assert health_of_maria() == 0
    r = client.put("/admin/retention", json={"divisions": {"b2c": {"atRiskDays": 30, "lostDays": 60}}}, headers=carmen)
    assert r.status_code == 200
    assert health_of_maria() == 1

    assert client.put("/admin/retention", json={"divisions": {"b2c": {"atRiskDays": 60, "lostDays": 30}}}, headers=carmen).status_code == 422
    assert client.put("/admin/retention", json={"divisions": {"finance": {"atRiskDays": 5, "lostDays": 10}}}, headers=carmen).status_code == 422


def test_the_demo_history_gives_the_figures_something_to_show(app, client, as_, records, settings):
    from app.seed import seed_demo_history

    with app.state.sessions() as db:
        set_company(db, FIRST_ORG_ID)
        assert seed_demo_history(records, db, settings) is True
        assert seed_demo_history(records, db, settings) is False  # only once
    body = client.get("/retention?division=bnb&view=team", headers=as_("lorna")).json()
    assert body["summary"]["base"] > 0 and body["summary"]["rate"] is not None
    assert {w["name"] for w in body["watch"]} >= {"Dr. Irene Galang", "Mercado Family Clinic", "Dr. Victor Salcedo"}
    # History quotes open like any other.
    alma = all_customers(records)["Dr. Alma Dizon"]
    quote_id = client.get(f"/sales/customers/{alma['_id']}", headers=as_("lorna")).json()["quotes"][0]["id"]
    assert client.get(f"/sales/quotes/{quote_id}", headers=as_("lorna")).status_code == 200


def test_reports_is_for_sales_modules_only(client, as_):
    carmen = as_("carmen")
    matrix = client.get("/admin/roles", headers=carmen).json()
    assert "report" in matrix["actions"]
    assert "report" in matrix["permissions"]["team_lead"]["bnb"] and "report" not in matrix["permissions"]["rep"]["bnb"]
    bad = {"permissions": {"department_staff": {"finance": ["view", "report"]}}}
    assert client.put("/admin/permissions", json=bad, headers=carmen).status_code == 422
