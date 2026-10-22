"""The playbooks' scorecards (app/scorecards.py, seeded by app.tools.seed_scorecards):
a person's month scored on their division's card from Finance's invoices,
with caps, bands, coaches scored on their district, and who sold nothing."""

import pytest

from app import finance
from app.models import Role, RolePermission, Team, User
from app.security import hash_password
from app.tools.seed_scorecards import seed
from tests.conftest import PASSWORD, bearer, role_id, sign_in
from tests.test_customers import crew  # noqa: F401 (crew is a fixture)

MONTH = "2026-09"  # over: 26 working days (Monday to Saturday)


def invoice(day, customer, who, total=400000, status="issued"):
    return {"id": f"{who}-{customer}-{day}", "status": status, "date": f"2026-09-{day}", "customerId": customer, "salespersonId": who, "totalCentavos": total, "termsDays": 30}


@pytest.fixture
def b2b(app, client, monkeypatch, crew):  # noqa: F811
    """B2B with its NBD branch: Ria and Rex sell there, Dee coaches the district. Finance's invoices are stood in for."""
    with app.state.sessions() as db:
        division = Team(name="B2B")
        db.add(division)
        db.flush()
        nbd = Team(name="B2B NBD", parent_id=division.id)
        lead = db.get(Role, role_id(db, "Team Lead"))
        coach = Role(name="District coach", scope=lead.scope, grants=[RolePermission(permission=p) for p in lead.permissions])
        db.add_all([nbd, coach])
        db.flush()
        for u in db.query(User).filter(User.email.in_(["ria@example.com", "rex@example.com"])):
            u.team_id = nbd.id
        db.add(User(email="dee@example.com", full_name="Dee", password_hash=hash_password(PASSWORD), role_id=coach.id, team_id=division.id))
        seed(db)
        db.commit()
        ids = {u.full_name: u.id for u in db.query(User)}
    ria = ids["Ria"]
    feeds = {
        "2026-09-01": {
            "invoices": [invoice("02", "c1", ria), invoice("03", "c2", ria), invoice("04", "c1", ria), invoice("05", "c9", ria, status="void")],
            "firstSale": {"c1": "2026-01-10", "c2": "2026-09-03"},
            "owed": {ria: 600000},
        },
        "2026-08-01": {"invoices": [invoice("10", "c1", ria), invoice("11", "c3", ria)], "firstSale": {}, "owed": {}},
    }
    monkeypatch.setattr(finance, "sales_feed", lambda settings, first, after: feeds.get(first))
    headers = dict(crew, dee=bearer(sign_in(client, "dee@example.com")))
    return ids, headers


def targets(client, ana, ids, kpi_codes):
    kpis = {k["code"]: k["id"] for k in client.get("/kpis?all=true", headers=ana).json()["items"]}
    body = [{"kpiId": kpis[code], "userId": ids[name], "value": value} for code, name, value in kpi_codes]
    r = client.put(f"/kpi-targets?month={MONTH}", json={"targets": body}, headers=ana)
    assert r.status_code == 200, r.text


def test_a_rep_is_scored_on_their_divisions_card(client, ana, b2b):
    ids, who = b2b
    targets(client, ana, ids, [("ist", "Ria", 1000000), ("nbd", "Ria", 1)])
    r = client.get(f"/scorecards?month={MONTH}", headers=who["ria"])
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["card"]["code"] == "b2b_nbd_chc" and [p["person"]["name"] for p in got["people"]] == ["Ria"]  # a rep sees their own
    ria = got["people"][0]
    items = {i["kpi"]: i for i in ria["items"]}
    assert (items["ist"]["actual"], items["ist"]["x"], items["ist"]["points"]) == (1200000, 120.0, 30)  # 3 invoices of ₱4,000 against ₱10,000
    assert (items["nbd"]["actual"], items["nbd"]["points"]) == (1, 30)  # c2's first sale ever
    assert (items["dso"]["actual"], items["dso"]["points"]) == (15, 20)  # ₱6,000 owed over ₱12,000 sold in 30 days
    assert (items["crr"]["actual"], items["crr"]["points"]) == (50, 0)  # c1 came back, c3 didn't
    assert (items["nzsd_500"]["actual"], items["nzsd_500"]["points"]) == (12, 0)  # 3 of 26 days
    assert (ria["total"], ria["outOf"], ria["band"]["label"]) == (80, 100, "Proficient")


def test_a_missed_gate_caps_the_month_and_a_coach_is_scored_on_the_district(client, ana, b2b):
    ids, who = b2b
    targets(client, ana, ids, [("ist", "Ria", 3000000), ("nbd", "Ria", 1)])  # 40% of IST: no IST points, and the month is capped at 40
    ria = client.get(f"/scorecards?month={MONTH}", headers=who["ria"]).json()["people"][0]
    assert ria["cap"]["total"] == 40 and ria["total"] == 40 and ria["band"]["pip"] is True

    coach = client.get(f"/scorecards?month={MONTH}&card=b2b_dsc", headers=who["dee"]).json()
    assert coach["card"]["code"] == "b2b_dsc"
    dee = next(p for p in coach["people"] if p["person"]["name"] == "Dee")
    items = {(i["kpi"], i["scope"]): i for i in dee["items"]}
    assert items[("ist", "team")]["x"] == 40.0 and dee["cap"]["total"] == 30  # the district's sales against its people's targets
    assert items[("ist", "team_average")]["x"] == 0  # Ria under 60%: TTAR is 0
    # Who sold nothing this month, of the people in reach.
    assert {p["name"] for p in coach["noSales"]} == {"Dee"}
    everyone = client.get(f"/scorecards?month={MONTH}", headers=ana).json()
    assert {"Rex", "Dee"} <= {p["name"] for p in everyone["noSales"]} and "Ria" not in {p["name"] for p in everyone["noSales"]}


def test_without_finance_the_sales_measures_show_nothing(client, ana, b2b, monkeypatch):
    ids, who = b2b
    monkeypatch.setattr(finance, "sales_feed", lambda *a: None)
    got = client.get(f"/scorecards?month={MONTH}", headers=who["ria"]).json()
    assert got["financeLinked"] is False and got["noSales"] is None
    assert {i["kpi"]: i["missing"] for i in got["people"][0]["items"]}["dso"] == "No result yet."
