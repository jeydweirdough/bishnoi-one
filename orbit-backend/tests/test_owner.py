"""Who owns a company, as against who runs it.

A System Admin runs a company: its people, roles, teams and lists. Its owner
decides what the company *is* — its name, how its money reads, its data going in
and out. The difference matters because an admin can edit the permission matrix,
so anything an admin could grant themselves is not a boundary at all.
"""


def me(client, headers) -> dict:
    return client.get("/auth/me", headers=headers).json()


def person(client, headers, email: str) -> dict:
    return next(u for u in client.get("/admin/users", headers=headers).json() if u["email"] == email)


def test_the_company_has_an_owner_and_the_app_is_told(client, as_):
    carmen, lorna = as_("carmen"), as_("lorna")
    assert me(client, carmen)["isOwner"] is True
    assert me(client, lorna)["isOwner"] is False
    assert person(client, carmen, "carmen@pharmacrm.test")["isOwner"] is True


def test_only_the_owner_changes_what_the_company_is(client, as_):
    carmen, ben = as_("carmen"), as_("ben")
    assert client.get("/admin/company", headers=carmen).status_code == 200
    assert client.get("/admin/company", headers=ben).status_code == 403

    # and being made a System Admin is not enough
    body = {"roleKey": "admin", "moduleKey": "*", "divisionCode": None, "subdivisionCode": None}
    assert client.post(f"/admin/users/{person(client, carmen, 'ben@pharmacrm.test')['id']}/assignments",
                       json=body, headers=carmen).status_code == 201
    assert me(client, ben)["canManageSettings"] is True
    assert me(client, ben)["isOwner"] is False
    assert client.get("/admin/users", headers=ben).status_code == 200      # runs the company
    assert client.patch("/admin/company", json={"name": "Mine"}, headers=ben).status_code == 403


def test_an_admin_cannot_make_themselves_the_owner(client, as_):
    """The whole point: an admin can rewrite every role, so if owning were a
    role they could simply grant it to themselves."""
    carmen, ben = as_("carmen"), as_("ben")
    ben_id = person(client, carmen, "ben@pharmacrm.test")["id"]
    body = {"roleKey": "admin", "moduleKey": "*", "divisionCode": None, "subdivisionCode": None}
    client.post(f"/admin/users/{ben_id}/assignments", json=body, headers=carmen)

    assert client.put(f"/admin/users/{ben_id}/owner", params={"keep": True}, headers=ben).status_code == 403
    matrix = client.get("/admin/roles", headers=ben).json()["permissions"]
    matrix["admin"] = {**matrix["admin"], "settings": ["manage"]}
    client.put("/admin/permissions", json={"permissions": matrix}, headers=ben)
    assert me(client, ben)["isOwner"] is False
    assert client.patch("/admin/company", json={"name": "Mine"}, headers=ben).status_code == 403


def test_an_owner_trusts_someone_else_and_can_then_step_back(client, as_):
    carmen, lorna = as_("carmen"), as_("lorna")
    lorna_id = person(client, carmen, "lorna@pharmacrm.test")["id"]
    carmen_id = person(client, carmen, "carmen@pharmacrm.test")["id"]

    assert client.put(f"/admin/users/{lorna_id}/owner", params={"keep": True}, headers=carmen).status_code == 200
    assert me(client, lorna)["isOwner"] is True
    assert client.get("/admin/company", headers=lorna).status_code == 200

    # now there are two, so the first may step back
    assert client.put(f"/admin/users/{carmen_id}/owner", params={"keep": False}, headers=carmen).status_code == 200
    assert me(client, carmen)["isOwner"] is False
    assert client.get("/admin/company", headers=carmen).status_code == 403


def test_a_company_is_never_left_without_an_owner(client, as_):
    carmen = as_("carmen")
    carmen_id = person(client, carmen, "carmen@pharmacrm.test")["id"]
    r = client.put(f"/admin/users/{carmen_id}/owner", params={"keep": False}, headers=carmen)
    assert r.status_code == 409 and "own the company" in r.json()["detail"]

    # nor by switching the last owner off
    off = client.patch(f"/admin/users/{carmen_id}", json={"isActive": False}, headers=carmen)
    assert off.status_code == 409
