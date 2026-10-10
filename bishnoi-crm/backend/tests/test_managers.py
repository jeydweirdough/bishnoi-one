"""Managers: above team leads. A team lead reaches their own team; a manager
reaches every team they're the manager of, and its people."""

from sqlalchemy import select

from app.models import Role, Team, User
from app.security import hash_password
from tests.conftest import PASSWORD, bearer, role_id, sign_in
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)


def make_manager(app, client, ana, teams: list[str]) -> dict:
    """Mia, a Manager, over these teams (set as an administrator would)."""
    with app.state.sessions() as db:
        db.add(User(email="mia@example.com", full_name="Mia", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Manager")))
        db.commit()
        mia = db.scalar(select(User).where(User.email == "mia@example.com")).id
        ids = {t.name: t.id for t in db.scalars(select(Team))}
    for name in teams:
        r = client.patch(f"/admin/teams/{ids[name]}", json={"managerId": mia}, headers=ana)
        assert r.status_code == 200 and r.json()["manager"]["name"] == "Mia", r.text
    return bearer(sign_in(client, "mia@example.com"))


def names(client, headers) -> set[str]:
    return {c["name"] for c in client.get("/companies?limit=200", headers=headers).json()["items"]}


def test_a_manager_reaches_every_team_they_manage(app, client, ana, crew):
    company(client, crew["ria"], "North Clinic")
    company(client, crew["sam"], "South Clinic")
    mia = make_manager(app, client, ana, ["North", "South"])
    assert names(client, mia) >= {"North Clinic", "South Clinic"}
    # The team lead: only her own team.
    assert "South Clinic" not in names(client, crew["lia"]) and "North Clinic" in names(client, crew["lia"])
    # She can give a record to anyone in the teams she manages.
    people = {p["name"] for p in client.get("/people/assignable", headers=mia).json()}
    assert {"Ria", "Rex", "Lia", "Sam", "Mia"} <= people


def test_a_manager_over_one_team_only_reaches_that_one(app, client, ana, crew):
    company(client, crew["sam"], "South Clinic")
    mia = make_manager(app, client, ana, ["North"])
    assert "South Clinic" not in names(client, mia)


def test_only_someone_who_manages_teams_can_be_a_team_s_manager(app, client, ana, crew):
    with app.state.sessions() as db:
        ria = db.scalar(select(User).where(User.email == "ria@example.com")).id
        north = db.scalar(select(Team).where(Team.name == "North")).id
    r = client.patch(f"/admin/teams/{north}", json={"managerId": ria}, headers=ana)
    assert r.status_code == 422 and "managerId" in str(r.json())


def test_the_manager_role_is_there_to_start_from(client, ana):
    roles = {r["name"]: r for r in client.get("/admin/roles", headers=ana).json()["roles"]}
    assert roles["Manager"]["scope"] == "managed"


def test_roles_keep_their_permissions_through_every_migration(client, ben):
    """A migration that rebuilds the roles table (0046) must not take the permissions with it."""
    me = client.get("/auth/me", headers=ben).json()
    assert {"customers.view", "customers.create"} <= set(me["permissions"])


def test_the_teams_page_offers_people_who_manage_teams(app, client, ana, crew):
    make_manager(app, client, ana, [])
    assert [m["name"] for m in client.get("/admin/teams/managers", headers=ana).json()] == ["Mia"]


# --- a manager runs their department's settings (department.manage) ---------------------------


def team_ids(app) -> dict[str, str]:
    with app.state.sessions() as db:
        return {t.name: t.id for t in db.scalars(select(Team))}


def promo(team: str) -> dict:
    return {"name": f"{team} half off", "kind": "percent", "percentBp": 5000, "teamIds": [team]}


def test_a_manager_runs_their_own_departments_promos_only(app, client, ana, crew):
    mia = make_manager(app, client, ana, ["North"])
    ids = team_ids(app)
    made = client.post("/promos", json=promo(ids["North"]), headers=mia)
    assert made.status_code == 201, made.text
    assert client.put(f"/promos/{made.json()['id']}", json={**promo(ids["North"]), "name": "North third off"}, headers=mia).status_code == 200
    assert client.post("/promos", json=promo(ids["South"]), headers=mia).status_code == 422
    assert client.get("/promos", headers=mia).json()["can"]["edit"] is True
    # One shared with another department is the administrator's.
    shared = client.post("/promos", json={**promo(ids["North"]), "teamIds": [ids["North"], ids["South"]]}, headers=ana).json()
    assert client.delete(f"/promos/{shared['id']}", headers=mia).status_code == 403
    # A team lead sets no promos.
    assert client.post("/promos", json=promo(ids["North"]), headers=crew["lia"]).status_code == 403


def test_a_manager_sets_up_their_own_departments_quotation_templates(app, client, ana, crew):
    mia = make_manager(app, client, ana, ["North"])
    ids = team_ids(app)
    everyone = client.post("/admin/quote-templates", json={"name": "Any quote"}, headers=ana).json()
    assert client.post("/admin/quote-templates", json={"name": "South letter", "teamId": ids["South"]}, headers=mia).status_code == 422
    assert client.post("/admin/quote-templates", json={"name": "Any quote 2"}, headers=mia).status_code == 422
    north = client.post("/admin/quote-templates", json={"name": "North letter", "teamId": ids["North"]}, headers=mia)
    assert north.status_code == 201, north.text
    assert [t["name"] for t in client.get("/admin/quote-templates", headers=mia).json()["items"]] == ["North letter"]
    assert client.patch(f"/admin/quote-templates/{everyone['id']}", json={"name": "Mine now"}, headers=mia).status_code == 404
    assert client.get("/admin/quote-templates", headers=crew["lia"]).status_code == 403


def test_a_manager_sets_their_own_departments_attention_rules(app, client, ana, crew):
    mia = make_manager(app, client, ana, ["North"])
    ids = team_ids(app)
    rule = {"quietDays": 30, "noticeDays": 7, "clidpDays": 30, "stuckDays": 2}
    assert client.put("/admin/attention-rules", json={**rule, "teamId": ids["North"]}, headers=mia).status_code == 200
    assert client.put("/admin/attention-rules", json={**rule, "teamId": ids["South"]}, headers=mia).status_code == 422
    assert client.put("/admin/attention-rules", json=rule, headers=mia).status_code == 422
    seen = client.get("/admin/attention-rules", headers=mia).json()
    assert [d["team"]["name"] for d in seen["divisions"]] == ["North"] and seen["canSetEveryone"] is False


def test_a_department_keeps_its_own_retention_windows(app, client, ana, crew):
    mia = make_manager(app, client, ana, ["North"])
    ids = team_ids(app)
    assert client.put(f"/retention/windows/{ids['South']}", json={"atRiskDays": 10, "lostDays": 20}, headers=mia).status_code == 422
    assert client.put(f"/retention/windows/{ids['North']}", json={"atRiskDays": 20, "lostDays": 10}, headers=mia).status_code == 422
    got = client.put(f"/retention/windows/{ids['North']}", json={"atRiskDays": 10, "lostDays": 20}, headers=mia).json()
    assert [(t["name"], t["atRiskDays"], t["lostDays"]) for t in got["teams"]] == [("North", 10, 20)]
    company(client, crew["ria"], "North Clinic")
    rules = client.get("/retention?view=team", headers=mia).json()["rules"]
    assert {"atRiskDays": 10, "lostDays": 20, "division": ids["North"], "divisionName": "North"} in rules
    # Back to the company's.
    back = client.put(f"/retention/windows/{ids['North']}", json={"atRiskDays": None, "lostDays": None}, headers=mia).json()
    assert back["teams"][0]["own"] is False


def test_a_manager_sets_targets_for_their_own_departments_people_only(app, client, ana, crew):
    mia = make_manager(app, client, ana, ["North"])
    people = {p["person"]["name"] for p in client.get("/sales/targets", headers=mia).json()["people"]}
    assert "Ria" in people and "Sam" not in people
    with app.state.sessions() as db:
        sam = db.scalar(select(User).where(User.full_name == "Sam")).id
    assert client.put("/sales/targets", json={"targets": [{"userId": sam, "amountCentavos": 100}]}, headers=mia).status_code == 422
