"""Administration: users, roles and permissions, teams, and the audit log."""

from tests.conftest import PASSWORD, bearer, sign_in


def roles(client, headers) -> dict[str, dict]:
    return {r["name"]: r for r in client.get("/admin/roles", headers=headers).json()["roles"]}


def new_team(client, headers, name="B2C") -> dict:
    r = client.post("/admin/teams", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def new_user(client, headers, **overrides) -> dict:
    body = {"email": "cara@example.com", "fullName": "Cara Diaz", "roleId": roles(client, headers)["Salesperson"]["id"], "password": "a fine password", **overrides}
    r = client.post("/admin/users", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def audit_actions(client, headers) -> list[str]:
    return [e["action"] for e in client.get("/admin/audit", headers=headers).json()["items"]]


# --- who gets in ---


def test_only_roles_with_the_permission_get_in(client, ana, ben):
    for path in ("/admin/users", "/admin/roles", "/admin/teams", "/admin/audit"):
        assert client.get(path, headers=ana).status_code == 200, path
        assert client.get(path, headers=ben).status_code == 403, path
        assert client.get(path).status_code == 401, path


def test_managing_users_needs_only_admin_users(client, ana):
    only_users = client.post("/admin/roles", json={"name": "People desk", "scope": "own", "permissions": ["admin.users"]}, headers=ana).json()
    new_team(client, ana, "HOS")
    new_user(client, ana, email="pd@example.com", roleId=only_users["id"])
    pd = bearer(sign_in(client, "pd@example.com", "a fine password"))
    options = client.get("/admin/users/options", headers=pd).json()
    assert [r["name"] for r in options["roles"]][:2] == ["Administrator", "Team Lead"]
    assert [t["name"] for t in options["teams"]] == ["HOS"]
    assert client.get("/admin/roles", headers=pd).status_code == 403


def test_each_admin_job_is_its_own_permission(client, ana):
    teams_only = client.post("/admin/roles", json={"name": "Team keeper", "scope": "own", "permissions": ["admin.teams"]}, headers=ana).json()
    new_user(client, ana, email="tk@example.com", roleId=teams_only["id"])
    tk = bearer(sign_in(client, "tk@example.com", "a fine password"))
    assert client.get("/admin/teams", headers=tk).status_code == 200
    assert client.get("/admin/users", headers=tk).status_code == 403
    me = client.get("/auth/me", headers=tk).json()
    assert me["permissions"] == ["admin.teams"] and me["canManageSettings"] is True


# --- users ---


def test_add_a_person_who_can_then_sign_in(client, ana):
    team = new_team(client, ana)
    cara = new_user(client, ana, teamId=team["id"])
    assert (cara["role"]["name"], cara["team"]["name"], cara["isActive"]) == ("Salesperson", "B2C", True)
    me = client.get("/auth/me", headers=bearer(sign_in(client, "cara@example.com", "a fine password"))).json()
    assert me["team"]["name"] == "B2C" and "customers.view" in me["permissions"] and "admin.users" not in me["permissions"]
    assert "user.created" in audit_actions(client, ana)


def test_new_people_are_checked(client, ana):
    rep = roles(client, ana)["Salesperson"]["id"]
    base = {"email": "x@example.com", "fullName": "X", "roleId": rep, "password": "a fine password"}
    assert client.post("/admin/users", json={**base, "email": "ben@example.com"}, headers=ana).status_code == 422
    assert client.post("/admin/users", json={**base, "email": "not-an-email"}, headers=ana).status_code == 422
    assert client.post("/admin/users", json={**base, "password": "short"}, headers=ana).status_code == 422
    assert client.post("/admin/users", json={**base, "roleId": "nope"}, headers=ana).status_code == 422
    assert client.post("/admin/users", json={**base, "teamId": "nope"}, headers=ana).status_code == 422


def test_change_a_persons_role_and_team(client, ana, ben):
    team = new_team(client, ana)
    ben_id = next(u["id"] for u in client.get("/admin/users", headers=ana).json() if u["email"] == "ben@example.com")
    lead = roles(client, ana)["Team Lead"]["id"]
    r = client.patch(f"/admin/users/{ben_id}", json={"roleId": lead, "teamId": team["id"]}, headers=ana)
    assert r.status_code == 200 and r.json()["role"]["name"] == "Team Lead"
    # It applies on Ben's next click, no sign-in needed.
    me = client.get("/auth/me", headers=ben).json()
    assert me["role"]["scope"] == "team" and "customers.delete" in me["permissions"]
    entry = client.get("/admin/audit", headers=ana).json()["items"][0]
    assert (entry["action"], entry["target"], sorted(entry["fields"])) == ("user.updated", "ben@example.com", ["roleId", "teamId"])


def test_switching_someone_off_signs_them_out(client, ana, ben):
    ben_id = next(u["id"] for u in client.get("/admin/users", headers=ana).json() if u["email"] == "ben@example.com")
    assert client.patch(f"/admin/users/{ben_id}", json={"isActive": False}, headers=ana).status_code == 200
    assert client.get("/auth/me", headers=ben).status_code == 401
    assert sign_in(client, "ben@example.com").status_code == 401
    # Newest first: the refused sign-in, then the switch-off before it.
    assert audit_actions(client, ana)[:2] == ["auth.sign_in_failed", "user.switched_off"]


def test_you_cant_switch_yourself_off(client, ana):
    ana_id = client.get("/auth/me", headers=ana).json()["user"]["id"]
    r = client.patch(f"/admin/users/{ana_id}", json={"isActive": False}, headers=ana)
    assert r.status_code == 409


def test_nobody_can_take_away_the_last_administrator(client, ana):
    ana_id = client.get("/auth/me", headers=ana).json()["user"]["id"]
    rep = roles(client, ana)["Salesperson"]["id"]
    r = client.patch(f"/admin/users/{ana_id}", json={"roleId": rep}, headers=ana)
    assert r.status_code == 409 and "nobody able to manage" in r.json()["detail"]
    assert client.get("/auth/me", headers=ana).json()["role"]["name"] == "Administrator"
    # With a second administrator, it's fine.
    new_user(client, ana, roleId=roles(client, ana)["Administrator"]["id"])
    assert client.patch(f"/admin/users/{ana_id}", json={"roleId": rep}, headers=ana).status_code == 200


def test_resetting_a_password_ends_their_sessions(client, ana, ben):
    ben_id = next(u["id"] for u in client.get("/admin/users", headers=ana).json() if u["email"] == "ben@example.com")
    assert client.post(f"/admin/users/{ben_id}/password", json={"password": "short"}, headers=ana).status_code == 422
    assert client.post(f"/admin/users/{ben_id}/password", json={"password": "a brand new one"}, headers=ana).status_code == 204
    assert client.get("/auth/me", headers=ben).status_code == 401
    assert sign_in(client, "ben@example.com", PASSWORD).status_code == 401
    assert sign_in(client, "ben@example.com", "a brand new one").status_code == 200


# --- roles ---


def test_starting_roles_and_the_permission_catalogue(client, ana):
    data = client.get("/admin/roles", headers=ana).json()
    by_name = {r["name"]: r for r in data["roles"]}
    assert list(by_name) == ["Administrator", "Team Lead", "Field agent", "Salesperson"]
    assert by_name["Administrator"]["isSystem"] and "admin.audit" in by_name["Administrator"]["permissions"]
    assert (by_name["Salesperson"]["scope"], by_name["Team Lead"]["scope"]) == ("own", "team")
    assert "customers.delete" not in by_name["Salesperson"]["permissions"]
    areas = {a["key"] for a in data["catalogue"]}
    assert {"customers", "deals", "activities", "quotes", "orders", "reports", "admin"} <= areas
    # Areas with no screens are neither offered nor kept.
    assert not {"leads", "opportunities", "contracts", "documents", "automations", "integrations"} & areas
    assert [s["key"] for s in data["scopes"]] == ["own", "team", "all"]


def test_make_edit_and_delete_a_role(client, ana):
    r = client.post("/admin/roles", json={"name": "Auditor", "scope": "all", "permissions": ["reports.view", "admin.audit"]}, headers=ana)
    assert r.status_code == 201
    auditor = r.json()
    assert client.post("/admin/roles", json={"name": "auditor"}, headers=ana).status_code == 422  # names are unique
    assert client.post("/admin/roles", json={"name": "X", "permissions": ["made.up"]}, headers=ana).status_code == 422
    assert client.post("/admin/roles", json={"name": "X", "scope": "everyone"}, headers=ana).status_code == 422

    r = client.patch(f"/admin/roles/{auditor['id']}", json={"permissions": ["reports.view", "reports.export"], "scope": "team"}, headers=ana)
    assert r.status_code == 200 and r.json()["permissions"] == ["reports.export", "reports.view"]
    assert client.delete(f"/admin/roles/{auditor['id']}", headers=ana).status_code == 204
    assert "Auditor" not in roles(client, ana)
    assert audit_actions(client, ana)[:3] == ["role.deleted", "role.updated", "role.created"]


def test_a_role_in_use_cant_be_deleted(client, ana):
    rep = roles(client, ana)["Salesperson"]
    r = client.delete(f"/admin/roles/{rep['id']}", headers=ana)
    assert r.status_code == 409 and "1 person has this role" in r.json()["detail"]


def test_the_administrator_role_is_fixed(client, ana):
    admin = roles(client, ana)["Administrator"]
    assert client.patch(f"/admin/roles/{admin['id']}", json={"permissions": []}, headers=ana).status_code == 409
    assert client.patch(f"/admin/roles/{admin['id']}", json={"name": "Boss"}, headers=ana).status_code == 409
    assert client.delete(f"/admin/roles/{admin['id']}", headers=ana).status_code == 409
    assert client.patch(f"/admin/roles/{admin['id']}", json={"description": "The owners."}, headers=ana).status_code == 200


def test_taking_admin_away_from_the_only_admin_role_is_refused(client, ana):
    # Move Ana onto a custom role that holds administration, then try to strip it.
    keeper = client.post("/admin/roles", json={"name": "Keeper", "scope": "all", "permissions": ["admin.users", "admin.roles"]}, headers=ana).json()
    ana_id = client.get("/auth/me", headers=ana).json()["user"]["id"]
    assert client.patch(f"/admin/users/{ana_id}", json={"roleId": keeper["id"]}, headers=ana).status_code == 200
    r = client.patch(f"/admin/roles/{keeper['id']}", json={"permissions": ["admin.users"]}, headers=ana)
    assert r.status_code == 409
    assert set(roles(client, ana)["Keeper"]["permissions"]) == {"admin.users", "admin.roles"}


# --- teams ---


def test_teams(client, ana):
    team = new_team(client, ana, "HOS")
    assert client.post("/admin/teams", json={"name": "hos"}, headers=ana).status_code == 422
    new_user(client, ana, teamId=team["id"])
    listed = {t["name"]: t for t in client.get("/admin/teams", headers=ana).json()}
    assert listed["HOS"]["memberCount"] == 1

    # With someone in it, it can be switched off but not deleted; nobody new joins it then.
    assert client.delete(f"/admin/teams/{team['id']}", headers=ana).status_code == 409
    assert client.patch(f"/admin/teams/{team['id']}", json={"isActive": False}, headers=ana).status_code == 200
    rep = roles(client, ana)["Salesperson"]["id"]
    r = client.post("/admin/users", json={"email": "d@example.com", "fullName": "D", "roleId": rep, "teamId": team["id"], "password": "a fine password"}, headers=ana)
    assert r.status_code == 422

    empty = new_team(client, ana, "BID")
    assert client.delete(f"/admin/teams/{empty['id']}", headers=ana).status_code == 204
    assert audit_actions(client, ana)[:2] == ["team.deleted", "team.created"]


# --- the audit log ---


def test_audit_log_pages_and_filters(client, ana):
    for name in ("A", "B", "C"):
        new_team(client, ana, name)
    first = client.get("/admin/audit", params={"limit": 2}, headers=ana).json()
    assert first["more"] is True and [e["target"] for e in first["items"]] == ["C", "B"]
    second = client.get("/admin/audit", params={"limit": 2, "before": first["items"][-1]["id"]}, headers=ana).json()
    assert second["items"][0]["target"] == "A"
    teams_only = client.get("/admin/audit", params={"action": "team."}, headers=ana).json()["items"]
    assert {e["action"] for e in teams_only} == {"team.created"}


def test_sign_ins_are_audited(client, ana):
    sign_in(client, "ben@example.com", "wrong")
    actions = audit_actions(client, ana)
    assert "auth.sign_in_failed" in actions and "auth.signed_in" in actions


def test_times_carry_their_zone(client, ana):
    """So the screens don't read UTC as local time."""
    user = next(u for u in client.get("/admin/users", headers=ana).json() if u["email"] == "ana@example.com")
    entry = client.get("/admin/audit", headers=ana).json()["items"][0]
    for moment in (user["createdAt"], user["lastSignInAt"], entry["at"]):
        assert moment.endswith("+00:00"), moment



def test_a_team_has_headquarters(client, ana):
    team = client.post("/admin/teams", json={"name": "STC", "headquarters": ["Makati", " Cebu ", "makati", ""]}, headers=ana).json()
    assert team["headquarters"] == ["Makati", "Cebu"]  # each once, blanks dropped
    team = client.patch(f"/admin/teams/{team['id']}", json={"headquarters": ["Cebu", "Davao"]}, headers=ana).json()
    assert team["headquarters"] == ["Cebu", "Davao"]
    assert client.patch(f"/admin/teams/{team['id']}", json={"headquarters": []}, headers=ana).json()["headquarters"] == []
    assert client.post("/admin/teams", json={"name": "URO"}, headers=ana).json()["headquarters"] == []
