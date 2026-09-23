"""Insights: a lead sees their team's work; the admin sees everyone's."""

from tests.test_customers import activity, company, crew  # noqa: F401 (crew is a fixture)


def people(client, headers) -> dict:
    r = client.get("/insights/people", headers=headers)
    assert r.status_code == 200, r.text
    return {p["name"]: p for p in r.json()["people"]}


def test_a_lead_sees_what_their_team_did_and_has_to_do(client, crew, ana):
    ria_co = company(client, crew["ria"], "Ria Co")
    company(client, crew["sam"], "Sam Co")
    activity(client, crew["ria"], companyId=ria_co["id"])  # a call, done now
    activity(client, crew["ria"], kind="task", subject="Chase", at="2020-01-01T09:00", companyId=ria_co["id"])  # overdue
    assert client.get("/insights/people", headers=crew["ria"]).status_code == 403  # a salesperson: their own Home

    team = people(client, crew["lia"])
    assert set(team) == {"Ria", "Rex", "Lia"}  # her team, and herself; not Sam
    ria = team["Ria"]
    assert (ria["overdue"], ria["doneThisWeek"], ria["customers"], ria["doneByKind"]) == (1, 1, 1, {"call": 1})
    assert ria["lastActivityAt"] and ria["signInsThisWeek"] >= 1
    assert team["Rex"]["doneThisWeek"] == 0
    assert team["Lia"]["isMe"]

    everyone = people(client, ana)  # the admin
    assert {"Ria", "Sam", "Max", "Ana Reyes", "Ben Cruz"} <= set(everyone)
    totals = client.get("/insights/people", headers=ana).json()["totals"]
    assert (totals["overdue"], totals["customers"]) == (1, 2)
