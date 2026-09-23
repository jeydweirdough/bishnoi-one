from tests.conftest import price_list_in
def my_id(client, headers) -> str:
    return client.get("/auth/me", headers=headers).json()["user"]["id"]


def test_settings_are_admin_only(client, as_):
    assert client.get("/admin/users", headers=as_("ana")).status_code == 403
    assert client.get("/admin/users", headers=as_("ramon")).status_code == 403
    assert client.get("/admin/users", headers=as_("carmen")).status_code == 200


def test_create_person_and_they_can_sign_in(client, as_):
    carmen = as_("carmen")
    body = {
        "email": "Nina@PharmaCRM.test",
        "fullName": "Nina Garcia",
        "password": "longenough",
        "assignments": [{"roleKey": "rep", "moduleKey": "stc", "divisionCode": "stc", "subdivisionCode": "md-telesales"}],
    }
    r = client.post("/admin/users", json=body, headers=carmen)
    assert r.status_code == 201, r.text
    assert r.json()["assignments"][0]["scopeLabel"] == "STC · MD Telesales"
    assert client.post("/admin/users", json=body, headers=carmen).status_code == 409

    token = client.post("/auth/login", json={"email": "nina@pharmacrm.test", "password": "longenough"}).json()["accessToken"]
    items = client.get("/sales/customers?division=stc", headers={"Authorization": f"Bearer {token}"}).json()["items"]
    assert [c["name"] for c in items] == ["Dr. Hilda Ong"]


def test_assignment_rules(client, as_):
    carmen = as_("carmen")
    ben = my_id(client, as_("ben"))
    post = lambda body: client.post(f"/admin/users/{ben}/assignments", json=body, headers=carmen)
    # a team is always inside its division
    assert post({"roleKey": "rep", "moduleKey": "bnb", "subdivisionCode": "md-telesales"}).status_code == 422
    # a sales module only covers its own division
    assert post({"roleKey": "rep", "moduleKey": "bnb", "divisionCode": "b2c"}).status_code == 422
    # the team must exist in that division
    assert post({"roleKey": "rep", "moduleKey": "b2b", "divisionCode": "b2b", "subdivisionCode": "md-telesales"}).status_code == 422
    assert post({"roleKey": "rep", "moduleKey": "bnb", "divisionCode": "bnb", "subdivisionCode": "md-telesales"}).status_code == 201
    assert post({"roleKey": "rep", "moduleKey": "bnb", "divisionCode": "bnb", "subdivisionCode": "md-telesales"}).status_code == 409


def test_cannot_lock_everyone_out_of_settings(client, as_):
    carmen = as_("carmen")
    me = client.get(f"/admin/users/{my_id(client, carmen)}", headers=carmen).json()
    admin_assignment = me["assignments"][0]["id"]
    assert client.delete(f"/admin/assignments/{admin_assignment}", headers=carmen).status_code == 409
    assert client.patch(f"/admin/users/{me['id']}", json={"isActive": False}, headers=carmen).status_code == 409

    matrix = client.get("/admin/roles", headers=carmen).json()["permissions"]
    matrix["admin"] = {}
    assert client.put("/admin/permissions", json={"permissions": matrix}, headers=carmen).status_code == 409
    assert client.get("/admin/users", headers=carmen).status_code == 200


def test_permission_matrix_changes_take_effect(client, as_):
    carmen, ana = as_("carmen"), as_("ana")
    irene = next(
        c["id"] for c in client.get("/sales/customers?division=bnb", headers=ana).json()["items"] if c["name"] == "Dr. Irene Galang"
    )
    matrix = client.get("/admin/roles", headers=carmen).json()["permissions"]
    matrix["rep"]["bnb"] = ["view", "create", "edit", "delete"]
    assert client.put("/admin/permissions", json={"permissions": matrix}, headers=carmen).status_code == 200
    assert client.delete(f"/sales/customers/{irene}", headers=ana).status_code == 204


def test_matrix_rejects_nonsense(client, as_):
    carmen = as_("carmen")
    put = lambda m: client.put("/admin/permissions", json={"permissions": m}, headers=carmen).status_code
    assert put({"rep": {"bnb": ["fly"]}}) == 422
    assert put({"rep": {"nowhere": ["view"]}}) == 422
    assert put({"rep": {"bnb": ["edit"]}}) == 422  # edit without view
    assert put({"ghost": {"bnb": ["view"]}}) == 422


def test_roles_can_be_added_and_unused_ones_removed(client, as_):
    carmen = as_("carmen")
    r = client.post("/admin/roles", json={"name": "Area Manager"}, headers=carmen)
    assert r.status_code == 201 and "area_manager" in r.json()["permissions"]
    assert client.delete("/admin/roles/rep", headers=carmen).status_code == 409  # in use
    assert client.delete("/admin/roles/area_manager", headers=carmen).status_code == 200


def test_teams_and_headquarters(client, as_):
    carmen = as_("carmen")
    r = client.post("/admin/teams/b2b", json={"name": "Key Accounts"}, headers=carmen)
    assert r.status_code == 201
    b2b = next(d for d in r.json()["divisions"] if d["code"] == "b2b")
    assert "key-accounts" in [t["code"] for t in b2b["teams"]]
    assert client.post("/admin/teams/b2b", json={"name": "key accounts"}, headers=carmen).status_code == 409
    # the same team name in another division is a different team
    assert client.post("/admin/teams/hos", json={"name": "Key Accounts"}, headers=carmen).status_code == 201
    assert client.post("/admin/teams/b2b/key-accounts/headquarters", json={"name": "CEBU"}, headers=carmen).status_code == 201

    # a switched-off team can't take new customers
    assert client.patch("/admin/teams/bnb/general", json={"isActive": False}, headers=carmen).status_code == 200
    body = {"team": "general", "name": "Late Clinic", "kind": "clinic"}
    assert client.post("/sales/customers", json={"division": "bnb", **body}, headers=as_("lorna")).status_code == 422


def test_a_department_can_be_added_and_then_granted_and_staffed(client, as_):
    carmen, ben = as_("carmen"), as_("ben")
    r = client.post("/admin/departments", json={"name": "Marketing", "icon": "trend"}, headers=carmen)
    assert r.status_code == 201
    added = next(d for d in r.json()["divisions"] if d["code"] == "marketing")
    # it arrives ready to hold people: a department, switched on, with one team
    assert (added["kind"], added["isActive"], added["isBuiltIn"], added["icon"]) == ("department", True, False, "trend")
    assert [t["code"] for t in added["teams"]] == ["general"]
    assert client.post("/admin/departments", json={"name": "marketing"}, headers=carmen).status_code == 409

    # it can be granted in a role, and someone assigned to it
    matrix = client.get("/admin/roles", headers=carmen).json()
    assert [m["actions"] for m in matrix["modules"] if m["key"] == "marketing"] == [["view", "create", "edit", "delete"]]
    permissions = {**matrix["permissions"], "department_staff": {"marketing": ["view", "create", "edit"]}}
    assert client.put("/admin/permissions", json={"permissions": permissions}, headers=carmen).status_code == 200
    body = {"roleKey": "department_staff", "moduleKey": "marketing", "divisionCode": "marketing", "subdivisionCode": "general"}
    r = client.post(f"/admin/users/{my_id(client, ben)}/assignments", json=body, headers=carmen)
    assert r.status_code == 201
    assert "Marketing · General" in [a["scopeLabel"] for a in r.json()["assignments"]]
    assert "marketing" in [m["key"] for m in client.get("/auth/me", headers=ben).json()["modules"]]

    # renaming keeps the code, so nothing granted comes loose
    r = client.patch("/admin/departments/marketing", json={"name": "Brand & Marketing"}, headers=carmen)
    assert next(d for d in r.json()["divisions"] if d["code"] == "marketing")["name"] == "Brand & Marketing"

    # switched off, it leaves the catalogue but keeps its rows
    assert client.patch("/admin/departments/marketing", json={"isActive": False}, headers=carmen).status_code == 200
    assert "marketing" not in [m["key"] for m in client.get("/auth/me", headers=ben).json()["modules"]]
    assert "marketing" in [d["code"] for d in client.get("/org", headers=carmen).json()["divisions"]]
    assert client.patch("/admin/departments/marketing", json={"isActive": True}, headers=carmen).status_code == 200
    assert "marketing" in [m["key"] for m in client.get("/auth/me", headers=ben).json()["modules"]]


def test_a_built_in_department_can_be_renamed_but_not_switched_off(client, as_):
    carmen = as_("carmen")
    r = client.patch("/admin/departments/finance", json={"name": "Finance & Credit"}, headers=carmen)
    assert r.status_code == 200
    assert next(d for d in r.json()["divisions"] if d["code"] == "finance")["name"] == "Finance & Credit"
    # the new name is what every screen now calls it
    assert [m["name"] for m in client.get("/admin/roles", headers=carmen).json()["modules"] if m["key"] == "finance"] == [
        "Finance & Credit"
    ]
    assert client.patch("/admin/departments/finance", json={"isActive": False}, headers=carmen).status_code == 422


def test_team_scoped_admin_role_does_not_open_settings(client, as_):
    carmen, ben = as_("carmen"), as_("ben")
    body = {"roleKey": "admin", "moduleKey": "*", "divisionCode": "b2c", "subdivisionCode": "md-telesales"}
    assert client.post(f"/admin/users/{my_id(client, ben)}/assignments", json=body, headers=carmen).status_code == 201
    assert client.get("/auth/me", headers=ben).json()["canManageSettings"] is False
    assert client.get("/admin/users", headers=ben).status_code == 403


def test_password_reset_ends_existing_sessions(client, as_):
    import time

    ana = as_("ana")
    time.sleep(1.1)  # token times are whole seconds
    r = client.patch(f"/admin/users/{my_id(client, ana)}", json={"password": "a-new-password"}, headers=as_("carmen"))
    assert r.status_code == 200
    assert client.get("/auth/me", headers=ana).status_code == 401
    fresh = client.post("/auth/login", json={"email": "ana@pharmacrm.test", "password": "a-new-password"})
    assert fresh.status_code == 200


def test_a_company_adds_a_sales_division_and_sells_in_it(client, as_):
    """The last thing that was code rather than data. A new sales division must
    arrive able to do everything the six that shipped with Orbit can."""
    carmen, ben = as_("carmen"), as_("ben")
    r = client.post("/admin/departments", json={"name": "Veterinary", "kind": "sales"}, headers=carmen)
    assert r.status_code == 201, r.text
    added = next(d for d in r.json()["divisions"] if d["code"] == "veterinary")
    assert (added["kind"], added["isBuiltIn"]) == ("sales", False)
    assert [t["code"] for t in added["teams"]] == ["general"]

    # it counts as a sales division everywhere that asks
    assert "veterinary" in [d["code"] for d in client.get("/admin/goals", headers=carmen).json()["divisions"]]
    retention = client.get("/admin/retention", headers=carmen).json()
    assert "veterinary" in [d["code"] for d in retention["divisions"]]

    # a role can be granted in it, and someone assigned
    matrix = client.get("/admin/roles", headers=carmen).json()
    assert "report" in [m for m in matrix["modules"] if m["key"] == "veterinary"][0]["actions"]
    permissions = {**matrix["permissions"], "rep": {**matrix["permissions"]["rep"], "veterinary": ["view", "create", "edit"]}}
    assert client.put("/admin/permissions", json={"permissions": permissions}, headers=carmen).status_code == 200
    body = {"roleKey": "rep", "moduleKey": "veterinary", "divisionCode": "veterinary", "subdivisionCode": "general"}
    assert client.post(f"/admin/users/{my_id(client, ben)}/assignments", json=body, headers=carmen).status_code == 201

    # and the workspace works: a customer can be added and found
    mine = [m["key"] for m in client.get("/auth/me", headers=ben).json()["modules"]]
    assert "veterinary" in mine
    made = client.post("/sales/customers", json={"division": "veterinary", "team": "general", "name": "Pet Clinic", "kind": "clinic"}, headers=ben)
    assert made.status_code == 201, made.text
    assert [c["name"] for c in client.get("/sales/customers?division=veterinary", headers=ben).json()["items"]] == ["Pet Clinic"]

    # its pricing rules exist but hold no price types: that is an admin's choice,
    # so the price list says so rather than pretending
    prices = price_list_in(client, ben, "veterinary")
    assert prices["priceTypes"] == []


def test_a_department_admin_runs_one_department(client, as_):
    """D1: settings, over a division.

    The access engine understood this before anything could create it -- the
    writer refused every scoped settings grant. This walks the whole path:
    the grant is written, it comes back on the person, and it resolves into
    `manageDepartments` without making them an admin of the company.
    """
    carmen = as_("carmen")
    ben = my_id(client, as_("ben"))
    post = lambda body: client.post(f"/admin/users/{ben}/assignments", json=body, headers=carmen)

    # A department is the smallest unit settings come in: not one of its teams.
    too_small = {"roleKey": "admin", "moduleKey": "settings", "divisionCode": "bnb", "subdivisionCode": "md-telesales"}
    assert post(too_small).status_code == 422

    # Recovery reaches the company record and every account, so it is never one
    # department's. No seeded role carries it -- a Developer Admin holds it from
    # the platform -- so the company makes one of its own to prove the refusal.
    assert client.post("/admin/roles", json={"name": "Tech Recovery"}, headers=carmen).status_code == 201
    client.put("/admin/permissions", json={"permissions": {"tech_recovery": {"settings": ["recover"]}}}, headers=carmen)
    assert post({"roleKey": "tech_recovery", "moduleKey": "settings", "divisionCode": "bnb"}).status_code == 422

    # And a role that runs no settings at all gains nothing from a department.
    assert post({"roleKey": "rep", "moduleKey": "settings", "divisionCode": "bnb"}).status_code == 422

    # The grant itself.
    r = post({"roleKey": "admin", "moduleKey": "settings", "divisionCode": "bnb"})
    assert r.status_code == 201, r.text
    assert any(a["moduleKey"] == "settings" for a in r.json()["assignments"])

    # And it resolves: one department, without running the company.
    token = client.post("/auth/login", json={"email": "ben@pharmacrm.test", "password": "demo1234"}).json()["accessToken"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["manageDepartments"] == ["bnb"]
    assert me["canManageSettings"] is False
    assert me["canRecover"] is False


def test_running_the_company_is_not_listed_as_running_each_department(client, as_):
    """A company-wide admin is covered by canManageSettings alone, so the two
    never have to be read together."""
    me = client.get("/auth/me", headers=as_("carmen")).json()
    assert me["canManageSettings"] is True
    assert me["manageDepartments"] == []


def test_a_position_is_a_job_title_and_grants_nothing(client, as_):
    """D3: positions.

    The whole point of the table is what it does NOT do. A person's title is
    recorded and reported on; it is never consulted when deciding what they may
    do. This proves both halves: the title sticks, and nothing about their
    access moves when it changes.
    """
    carmen = as_("carmen")
    ben_id = my_id(client, as_("ben"))

    def access_of(who="ben"):
        token = client.post("/auth/login", json={"email": f"{who}@pharmacrm.test", "password": "demo1234"}).json()["accessToken"]
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        return {
            "settings": me["canManageSettings"],
            "recover": me["canRecover"],
            "departments": me["manageDepartments"],
            "modules": sorted(m["key"] for m in me["modules"]),
        }

    before = access_of()

    # A department names a job.
    r = client.post("/admin/positions", json={"title": "Procurement Officer", "divisionCode": "bnb"}, headers=carmen)
    assert r.status_code == 201, r.text
    position = r.json()
    assert position["title"] == "Procurement Officer"
    assert position["divisionCode"] == "bnb"

    # Twice in the same department is one title too many.
    assert client.post("/admin/positions", json={"title": "Procurement Officer", "divisionCode": "bnb"}, headers=carmen).status_code == 409

    # Somebody holds it.
    r = client.patch(f"/admin/users/{ben_id}", json={"positionId": position["id"]}, headers=carmen)
    assert r.status_code == 200, r.text

    # And nothing whatsoever about their access moved.
    assert access_of() == before

    # Switched off, never deleted -- and then it cannot be handed out.
    assert client.patch(f"/admin/positions/{position['id']}", json={"isActive": False}, headers=carmen).status_code == 200
    assert client.patch(f"/admin/users/{ben_id}", json={"positionId": position["id"]}, headers=carmen).status_code == 422
    assert [p["title"] for p in client.get("/admin/positions", headers=carmen).json()["positions"]] == ["Procurement Officer"]
