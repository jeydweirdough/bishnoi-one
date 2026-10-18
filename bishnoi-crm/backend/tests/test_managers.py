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


def test_a_manager_runs_the_people_in_their_teams(app, client, ana, crew):
    # Like an administrator, for the teams she manages: their people, the roles below hers, those teams.
    mia = make_manager(app, client, ana, ["North"])
    people = {p["email"]: p for p in client.get("/admin/users", headers=mia).json()}
    assert "ria@example.com" in people and "lia@example.com" in people
    assert "sam@example.com" not in people and "mia@example.com" not in people and "ana@example.com" not in people
    options = client.get("/admin/users/options", headers=mia).json()
    roles = {r["name"]: r["id"] for r in options["roles"]}
    assert set(roles) >= {"Team Lead", "Salesperson", "Field agent"} and not {"Administrator", "Manager", "Finance"} & set(roles)
    assert [t["name"] for t in options["teams"]] == ["North"]
    with app.state.sessions() as db:
        ids = {t.name: t.id for t in db.scalars(select(Team))}
        admin_role = role_id(db, "Administrator")
    ria = people["ria@example.com"]["id"]

    # Her people: role, details, on and off, a new password.
    changed = client.patch(f"/admin/users/{ria}", json={"roleId": roles["Field agent"], "fullName": "Ria Santos"}, headers=mia)
    assert changed.status_code == 200 and changed.json()["role"]["name"] == "Field agent" and changed.json()["fullName"] == "Ria Santos"
    assert client.patch(f"/admin/users/{ria}", json={"isActive": False}, headers=mia).json()["isActive"] is False
    assert client.post(f"/admin/users/{ria}/password", json={"password": "a brand new phrase"}, headers=mia).status_code == 204
    # Not beyond her: another team, a role above, someone outside her teams, herself.
    assert client.patch(f"/admin/users/{ria}", json={"teamId": ids["South"]}, headers=mia).status_code == 422
    assert client.patch(f"/admin/users/{ria}", json={"roleId": admin_role}, headers=mia).status_code == 422
    sam = client.get("/admin/users", headers=ana).json()
    sam = next(p["id"] for p in sam if p["email"] == "sam@example.com")
    assert client.patch(f"/admin/users/{sam}", json={"fullName": "Not hers"}, headers=mia).status_code == 404
    # A new person: into her team, in a role she may give.
    new = {"email": "nina@example.com", "fullName": "Nina Cruz", "roleId": roles["Salesperson"], "teamId": ids["North"], "password": "a brand new phrase"}
    assert client.post("/admin/users", json=new, headers=mia).status_code == 201
    assert client.post("/admin/users", json={**new, "email": "nino@example.com", "teamId": None}, headers=mia).status_code == 422
    # A team lead isn't a manager: no people pages.
    assert client.get("/admin/users", headers=crew["lia"]).status_code == 403


def test_a_person_in_two_teams(app, client, ana, crew):
    # A team lead in North and South reaches both teams' records; what she makes stays in her main team.
    company(client, crew["sam"], "South Clinic")
    with app.state.sessions() as db:
        ids = {t.name: t.id for t in db.scalars(select(Team))}
        lia = db.scalar(select(User).where(User.email == "lia@example.com")).id
    assert "South Clinic" not in names(client, crew["lia"])
    saved = client.patch(f"/admin/users/{lia}", json={"otherTeamIds": [ids["South"]]}, headers=ana).json()
    assert saved["team"]["name"] == "North" and [t["name"] for t in saved["otherTeams"]] == ["South"]
    assert "South Clinic" in names(client, crew["lia"])
    made = company(client, crew["lia"], "Lia's Clinic")
    assert client.get(f"/companies/{made['id']}", headers=ana).json()["team"]["name"] == "North"
    # Both teams count her.
    teams = {t["name"]: t for t in client.get("/admin/teams", headers=ana).json()}
    assert teams["South"]["memberCount"] >= 2

    # A manager of North only adds and removes North; South stays as the admin set it.
    mia = make_manager(app, client, ana, ["North"])
    ria = next(p["id"] for p in client.get("/admin/users", headers=mia).json() if p["email"] == "ria@example.com")
    assert client.patch(f"/admin/users/{ria}", json={"otherTeamIds": [ids["South"]]}, headers=mia).status_code == 422
    assert client.patch(f"/admin/users/{lia}", json={"otherTeamIds": []}, headers=mia).json()["otherTeams"] == [{"id": ids["South"], "name": "South"}]


def test_a_manager_proposes_prices_and_finance_approves(app, client, ana, crew):
    # A manager sets a product's Doctor's and Patient's prices; they wait for Finance, so reps still see the old ones.
    from app.tools.users import make_demo_catalogue

    with app.state.sessions() as db:
        make_demo_catalogue(db)
    mia = make_manager(app, client, ana, ["North"])
    amox = next(p for p in client.get("/products", headers=mia).json()["items"] if p["code"] == "AMX-500")
    assert amox["can"]["propose"] is True and amox["can"]["edit"] is False
    r = client.put(f"/products/{amox['id']}/prices", json={"prices": {"DOCTOR": 125000, "PATIENT": 150000}}, headers=mia)
    assert r.status_code == 200, r.text
    waiting = r.json()["priceApprovals"]
    assert waiting["DOCTOR"]["status"] == "pending" and waiting["DOCTOR"]["proposedAmount"] == 125000
    # A rep still quotes the approved price.
    seen = next(p for p in client.get("/products", headers=crew["ria"]).json()["items"] if p["code"] == "AMX-500")
    assert seen["prices"].get("DOCTOR") != 125000 and seen["prices"].get("PATIENT") != 150000
    # The SRP is Finance's; a rep can't propose at all.
    assert client.put(f"/products/{amox['id']}/prices", json={"prices": {"SRP": 1}}, headers=mia).status_code == 422
    assert client.put(f"/products/{amox['id']}/prices", json={"prices": {"DOCTOR": 1}}, headers=crew["ria"]).status_code == 403


def test_a_manager_exports_and_imports_prices(app, client, ana, crew):
    # Export the products, change a price in the file, import it back: it goes to Finance; unchanged rows change nothing.
    import csv
    import io

    from app.tools.users import make_demo_catalogue

    with app.state.sessions() as db:
        make_demo_catalogue(db)
    mia = make_manager(app, client, ana, ["North"])
    r = client.get("/exports/products", params={"format": "csv"}, headers=mia)
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    head, body = rows[0], rows[1:]
    assert head[:7] == ["Code", "Name", "Generic name", "Strength", "Form", "Unit", "On sale"]
    doctor = head.index("Doctor's price") if "Doctor's price" in head else next(i for i, h in enumerate(head) if "octor" in h)
    amox = next(row for row in body if row[0] == "AMX-500")

    read = client.post("/imports/prices/read", files={"file": ("p.csv", r.content, "text/csv")}, headers=mia).json()
    assert "price:SRP" not in read["mapping"] and read["mapping"]["code"] == 0
    rows_back = read["rows"]
    unchanged = client.post("/imports/prices", json={"mapping": read["mapping"], "rows": rows_back, "dryRun": False}, headers=mia).json()
    assert unchanged["updated"] == 0 and unchanged["problems"] == []

    changed = [row[:] for row in rows_back]
    i = next(k for k, row in enumerate(changed) if row[0] == "AMX-500")
    changed[i][doctor] = "1,250.00"
    changed.append(["NOPE-1"] + [""] * (len(head) - 1))
    done = client.post("/imports/prices", json={"mapping": read["mapping"], "rows": changed, "dryRun": False}, headers=mia).json()
    assert done["updated"] == 1 and [p["message"] for p in done["problems"]] == ["Code NOPE-1 isn't a product here."]
    p = next(x for x in client.get("/products", headers=mia).json()["items"] if x["code"] == "AMX-500")
    waiting = [a for a in p["priceApprovals"].values() if a["status"] == "pending"]
    assert [a["proposedAmount"] for a in waiting] == [125000] and amox[0] == "AMX-500"
    # A rep can't import prices.
    assert client.post("/imports/prices/read", files={"file": ("p.csv", r.content, "text/csv")}, headers=crew["ria"]).status_code == 403
