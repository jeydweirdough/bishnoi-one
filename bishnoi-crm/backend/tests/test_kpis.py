"""KPI management: defining KPIs, targets for people and teams, results entered
by hand, and the scorecard."""

from tests.test_customers import activity, company, crew  # noqa: F401  (crew is a fixture)

MONTH = "2026-09"  # over, so results are judged against the whole target, not the pace


def kpis(client, headers, everything=False) -> dict:
    r = client.get(f"/kpis{'?all=true' if everything else ''}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def role(client, ana, name) -> str:
    return next(r["id"] for r in kpis(client, ana)["roles"] if r["name"] == name)


def make(client, ana, **body) -> dict:
    r = client.post("/admin/kpis", json={"measure": "activities", **body}, headers=ana)
    assert r.status_code == 201, r.text
    return r.json()


def call(client, headers, day="10", **extra):
    return activity(client, headers, kind="call", at=f"{MONTH}-{day}T03:00:00Z", **extra)


def test_the_field_goals_and_revenue_target_are_built_in_kpis(client, ana):
    got = {k["code"]: k for k in kpis(client, ana)["items"]}
    assert set(got) == {"revenue_won", "doctors_visited", "doctors_updated", "amount_collected", "collection_visits"}
    assert (got["revenue_won"]["unit"], got["amount_collected"]["unit"]) == ("money", "money")
    assert [r["name"] for r in got["doctors_visited"]["roles"]] == ["Field agent"]
    assert {r["name"] for r in got["revenue_won"]["roles"]} >= {"Salesperson", "Team Lead"}
    # A built-in KPI keeps what it measures and can't be deleted, but can be renamed or switched off.
    rev = got["revenue_won"]["id"]
    assert client.patch(f"/admin/kpis/{rev}", json={"measure": "quotes"}, headers=ana).status_code == 409
    assert client.delete(f"/admin/kpis/{rev}", headers=ana).status_code == 409
    assert client.patch(f"/admin/kpis/{rev}", json={"name": "Sales won", "greenAt": 95}, headers=ana).json()["name"] == "Sales won"


def test_an_administrator_defines_kpis_and_bad_ones_are_refused(client, crew, ana):
    sales = role(client, ana, "Salesperson")
    calls = make(client, ana, name="Calls made", filters={"kind": "call"}, roles=[sales], amberAt=70)
    assert (calls["measureLabel"], calls["filterLabel"], calls["unit"], calls["roles"][0]["name"]) == ("Activities done", "Call", "count", "Salesperson")
    bad = [
        {"name": "x", "measure": "nonsense"},
        {"name": "x", "measure": "quotes", "filters": {"kind": "call"}},
        {"name": "x", "measure": "activities", "filters": {"kind": "fax"}},
        {"name": "x", "measure": "visits", "greenAt": 80, "amberAt": 90},
        {"name": "calls made", "measure": "visits"},
    ]
    for body in bad:
        assert client.post("/admin/kpis", json=body, headers=ana).status_code == 422, body
    # Defining KPIs is an administrator's; a team lead can't.
    assert client.post("/admin/kpis", json={"name": "Mine", "measure": "visits"}, headers=crew["lia"]).status_code == 403
    assert client.delete(f"/admin/kpis/{calls['id']}", headers=ana).status_code == 204


def test_targets_and_the_scorecard_for_people_and_teams(client, crew, ana):
    sales = role(client, ana, "Salesperson")
    calls = make(client, ana, name="Calls made", filters={"kind": "call"}, roles=[sales])
    ids = {p["person"]["name"]: p["person"]["id"] for p in client.get(f"/kpi-targets?month={MONTH}", headers=ana).json()["people"]}
    r = client.put(
        f"/kpi-targets?month={MONTH}",
        json={"targets": [{"kpiId": calls["id"], "userId": ids["Ria"], "value": 10}, {"kpiId": calls["id"], "userId": ids["Rex"], "value": 5}]},
        headers=ana,
    )
    assert r.status_code == 200, r.text
    acme = company(client, crew["ria"])["id"]
    for day in ("02", "03", "04", "05", "06", "07", "08", "09"):
        call(client, crew["ria"], day=day, companyId=acme)
    for day in ("02", "03"):
        call(client, crew["rex"], day=day)
    activity(client, crew["ria"], kind="note", at=f"{MONTH}-10T03:00:00Z")  # not a call

    mine = client.get(f"/kpi-scorecard?month={MONTH}", headers=crew["ria"]).json()
    ria = mine["people"][0]["results"][calls["id"]]
    assert (ria["actual"], ria["target"], ria["attainment"], ria["status"]) == (8, 10, 80, "amber")
    # A salesperson sees their own; a team lead their team.
    assert client.get(f"/kpi-scorecard?month={MONTH}&view=team", headers=crew["ria"]).status_code == 403
    team = client.get(f"/kpi-scorecard?month={MONTH}&view=team", headers=crew["lia"]).json()
    rows = {p["person"]["name"]: p["results"].get(calls["id"]) for p in team["people"]}
    # One role at a time, the biggest first: salespeople, with their KPIs only.
    assert [r["name"] for r in team["roles"]] == ["Salesperson", "Team Lead"]
    assert set(rows) == {"Ria", "Rex"} and rows["Rex"]["status"] == "red"
    leads = client.get(f"/kpi-scorecard?month={MONTH}&view=team&role={team['roles'][1]['id']}", headers=crew["lia"]).json()
    assert [p["person"]["name"] for p in leads["people"]] == ["Lia"]
    assert calls["id"] not in {k["id"] for k in leads["kpis"]}  # Calls made is for salespeople only
    north = next(t for t in team["teams"] if t["team"] and t["team"]["name"] == "North")["results"][calls["id"]]
    assert (north["actual"], north["target"], north["ownTarget"]) == (10, 15, False)

    # A team's own target stands over its people's added up.
    north_id = next(t["team"]["id"] for t in client.get(f"/kpi-targets?month={MONTH}", headers=ana).json()["teams"] if t["team"]["name"] == "North")
    client.put(f"/kpi-targets?month={MONTH}", json={"targets": [{"kpiId": calls["id"], "teamId": north_id, "value": 12}]}, headers=ana)
    team = client.get(f"/kpi-scorecard?month={MONTH}&view=team", headers=crew["lia"]).json()
    north = next(t for t in team["teams"] if t["team"] and t["team"]["name"] == "North")["results"][calls["id"]]
    assert (north["target"], north["ownTarget"], north["status"]) == (12, True, "amber")
    # Setting targets is for whoever sets goals.
    assert client.put(f"/kpi-targets?month={MONTH}", json={"targets": []}, headers=crew["lia"]).status_code == 403


def test_a_kpi_entered_by_hand(client, crew, ana):
    events = make(client, ana, name="Clinic events held", measure="manual", unit="count")
    ria = next(p["person"]["id"] for p in client.get(f"/kpi-targets?month={MONTH}", headers=ana).json()["people"] if p["person"]["name"] == "Ria")
    client.put(f"/kpi-targets?month={MONTH}", json={"targets": [{"kpiId": events["id"], "userId": ria, "value": 2}]}, headers=ana)
    r = client.put(f"/kpi-entries?month={MONTH}", json={"entries": [{"kpiId": events["id"], "userId": ria, "value": 3}]}, headers=ana)
    assert r.status_code == 200, r.text
    got = client.get(f"/kpi-scorecard?month={MONTH}", headers=crew["ria"]).json()["people"][0]["results"][events["id"]]
    assert (got["actual"], got["status"]) == (3, "green")
    # Only a manual KPI takes results by hand.
    calls = make(client, ana, name="Calls", filters={"kind": "call"})
    assert client.put(f"/kpi-entries?month={MONTH}", json={"entries": [{"kpiId": calls["id"], "userId": ria, "value": 3}]}, headers=ana).status_code == 422


def test_lower_is_better_and_a_rate_kpi(client, crew, ana):
    rate = make(client, ana, name="Win rate", measure="win_rate")
    assert rate["unit"] == "percent"
    ria = next(p["person"]["id"] for p in client.get(f"/kpi-targets?month={MONTH}", headers=ana).json()["people"] if p["person"]["name"] == "Ria")
    assert client.put(f"/kpi-targets?month={MONTH}", json={"targets": [{"kpiId": rate["id"], "userId": ria, "value": 140}]}, headers=ana).status_code == 422
    # No deals decided: no rate yet, so nothing to judge.
    got = client.get(f"/kpi-scorecard?month={MONTH}", headers=crew["ria"]).json()["people"][0]["results"][rate["id"]]
    assert got["actual"] is None


def test_revenue_targets_set_the_old_way_are_the_revenue_won_kpi(client, crew, ana):
    ria = next(p["person"]["id"] for p in client.get("/sales/targets?month=2026-10", headers=ana).json()["people"] if p["person"]["name"] == "Ria")
    client.put("/sales/targets?month=2026-10", json={"targets": [{"userId": ria, "amountCentavos": 5_000_00}]}, headers=ana)
    board = client.get("/kpi-targets?month=2026-10", headers=ana).json()
    rev = next(k["id"] for k in board["kpis"] if k["code"] == "revenue_won")
    assert next(p for p in board["people"] if p["person"]["id"] == ria)["targets"][rev] == 500000
