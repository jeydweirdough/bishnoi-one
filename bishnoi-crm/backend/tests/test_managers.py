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
