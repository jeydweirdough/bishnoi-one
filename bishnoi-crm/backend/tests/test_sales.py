"""Sales results: revenue targets, what was won and lost against them, by
person, team, customer and product, and the CSV exports. Also the deal views'
team and owner filters the results lean on."""

from datetime import date

from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)
from tests.test_deals import deal
from tests.test_quotes import catalogue, ids, line, save  # noqa: F401 (fixtures)

MONTH = date.today().isoformat()[:7]


def target(client, headers, person_id, amount, month=MONTH):
    r = client.put(f"/sales/targets?month={month}", json={"targets": [{"userId": person_id, "amountCentavos": amount}]}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def person_id(client, headers, name) -> str:
    return next(p["person"]["id"] for p in client.get(f"/sales/targets?month={MONTH}", headers=headers).json()["people"] if p["person"]["name"] == name)


def win(client, headers, d, **body):
    r = client.post(f"/deals/{d['id']}/win", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def lose(client, headers, d, reason="Price"):
    r = client.post(f"/deals/{d['id']}/lose", json={"reason": reason}, headers=headers)
    assert r.status_code == 200, r.text


def test_targets_are_set_by_whoever_sets_goals(client, crew, ana):
    people = {p["person"]["name"]: p for p in client.get("/sales/targets", headers=ana).json()["people"]}
    assert {"Ria", "Rex", "Lia", "Sam", "Ben Cruz"} <= set(people)  # everyone who sells
    assert "Ana Reyes" not in people  # the Administrator role isn't a seller
    got = target(client, ana, people["Ria"]["person"]["id"], 1_000_000)
    assert next(p for p in got["people"] if p["person"]["name"] == "Ria")["targetCentavos"] == 1_000_000
    cleared = target(client, ana, people["Ria"]["person"]["id"], None)
    assert next(p for p in cleared["people"] if p["person"]["name"] == "Ria")["targetCentavos"] is None
    assert client.get("/sales/targets", headers=crew["ria"]).status_code == 403


def test_my_results_against_my_target(client, crew, ana):
    target(client, ana, person_id(client, ana, "Ria"), 100_000)
    acme = company(client, crew["ria"])
    win(client, crew["ria"], deal(client, crew["ria"], acme, name="A", valueCentavos=30_000))
    win(client, crew["ria"], deal(client, crew["ria"], acme, name="B", valueCentavos=20_000))
    lose(client, crew["ria"], deal(client, crew["ria"], acme, name="C", valueCentavos=40_000), "Went with a competitor")
    deal(client, crew["ria"], acme, name="Open", valueCentavos=99_999)  # still open: not a result
    win(client, crew["rex"], deal(client, crew["rex"], company(client, crew["rex"], "Rex co"), valueCentavos=5_000))  # someone else's
    r = client.get(f"/sales/results?period={MONTH}", headers=crew["ria"]).json()
    t = r["totals"]
    assert (t["wonCentavos"], t["wonCount"], t["lostCentavos"], t["lostCount"], t["winRate"]) == (50_000, 2, 40_000, 1, 67)
    assert (t["targetCentavos"], t["attainment"]) == (100_000, 50)
    assert [p["person"]["name"] for p in r["people"]] == ["Ria"]
    assert r["customers"] == [{"customer": {"id": acme["id"], "name": "Acme"}, "wonCentavos": 50_000, "wonCount": 2}]
    assert r["lostReasons"] == [{"reason": "Went with a competitor", "count": 1, "lostCentavos": 40_000}]
    assert r["canExport"]


def test_a_team_lead_sees_the_team_and_a_rep_does_not(client, crew, ana):
    target(client, ana, person_id(client, ana, "Ria"), 50_000)
    target(client, ana, person_id(client, ana, "Rex"), 50_000)
    win(client, crew["ria"], deal(client, crew["ria"], company(client, crew["ria"]), valueCentavos=10_000))
    win(client, crew["rex"], deal(client, crew["rex"], company(client, crew["rex"], "Rex co"), valueCentavos=30_000))
    win(client, crew["sam"], deal(client, crew["sam"], company(client, crew["sam"], "Sam co"), valueCentavos=70_000))
    r = client.get(f"/sales/results?view=team&period={MONTH}", headers=crew["lia"]).json()
    by = {p["person"]["name"]: p for p in r["people"]}
    assert set(by) == {"Ria", "Rex", "Lia"}  # her team: Sam is South's
    assert (by["Rex"]["wonCentavos"], by["Rex"]["attainment"]) == (30_000, 60)
    assert (r["totals"]["wonCentavos"], r["totals"]["targetCentavos"], r["totals"]["attainment"]) == (40_000, 100_000, 40)
    assert [(t["team"]["name"], t["wonCentavos"], t["targetCentavos"]) for t in r["teams"]] == [("North", 40_000, 100_000)]
    assert client.get("/sales/results?view=team", headers=crew["ria"]).status_code == 403
    # Someone who sees every team can look at one.
    south = client.get(f"/sales/results?view=team&period={MONTH}&team={by['Ria']['team']['id']}", headers=crew["max"]).json()
    assert south["totals"]["wonCentavos"] == 40_000


def test_revenue_by_product_comes_from_the_winning_quote_or_the_deal(client, crew, ids):
    acme = company(client, crew["ria"])
    quoted = deal(client, crew["ria"], acme, name="Quoted")
    quote = save(client, crew["ria"], acme, [line(ids["AMX-500"], 2)], dealId=quoted["id"]).json()
    win(client, crew["ria"], quoted, quoteId=quote["id"])
    win(client, crew["ria"], deal(client, crew["ria"], acme, name="Lines", priceType="PATIENT", lines=[line(ids["CTZ-10"], 3)]))
    win(client, crew["ria"], deal(client, crew["ria"], acme, name="Typed", valueCentavos=12_345))
    products = {p["product"]["name"]: p for p in client.get(f"/sales/results?period={MONTH}", headers=crew["ria"]).json()["products"]}
    amox = products["Amoxil"]
    assert (amox["quantity"], amox["wonCentavos"]) == (2, quote["lines"][0]["totalCentavos"])
    assert products["Cetrin"]["quantity"] == 3
    assert products["Not itemised"]["wonCentavos"] == 12_345


def test_results_export_as_csv(client, crew, ana):
    win(client, crew["ria"], deal(client, crew["ria"], company(client, crew["ria"]), valueCentavos=10_000))
    r = client.get(f"/sales/results/export?report=people&period={MONTH}", headers=crew["ria"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = r.text.lstrip("﻿").splitlines()
    assert rows[0].startswith("Person,Team,Target,Won,Attainment") and rows[1].startswith("Ria,North,,100.00,")
    customers = client.get(f"/sales/results/export?report=customers&view=team&period={MONTH}", headers=crew["lia"])
    assert customers.status_code == 200 and "Acme,100.00,1" in customers.text
    assert client.get("/sales/results/export?report=people&view=team", headers=crew["ria"]).status_code == 403


def test_deal_views_filter_by_owner_and_team(client, crew):
    deal(client, crew["ria"], company(client, crew["ria"]), name="North deal", valueCentavos=100)
    deal(client, crew["sam"], company(client, crew["sam"], "Sam co"), name="South deal", valueCentavos=200)
    assert {d["name"] for d in client.get("/deals", headers=crew["max"]).json()["items"]} == {"North deal", "South deal"}
    # The team filter: the board, the list and the forecast agree.
    by_team = lambda path: client.get(path, headers=crew["max"]).json()  # noqa: E731
    north_team = client.get("/sales/results?view=team", headers=crew["lia"]).json()["people"][0]["team"]["id"]
    assert {d["name"] for d in by_team(f"/deals?team={north_team}")["items"]} == {"North deal"}
    board = by_team(f"/deals-board?team={north_team}")
    assert sum(c["count"] for c in board["columns"]) == 1
    assert by_team(f"/deals-forecast?team={north_team}")["totals"]["pipelineCentavos"] == 100
    # "Mine" in the forecast is mine, not my team's.
    assert client.get("/deals-forecast?owner=me", headers=crew["lia"]).json()["totals"]["deals"] == 0
