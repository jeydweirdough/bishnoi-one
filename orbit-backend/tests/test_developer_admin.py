"""Developer Admin: the tier above every company.

Orbit runs many companies. An Admin runs one of them and reaches nothing
outside it. A Developer Admin reaches all of them -- to fix a broken link to
another application, to read a log, to put an account back -- and inside each
one holds only the recovery screens, never its prices or its permission matrix.

The thing these tests are really guarding is that it is **not a role**. A
company's Admin edits the permission matrix, so anything grantable through a
role is something they could grant themselves, and a company promoting its own
staff to reach every other company would make the wall decoration.
"""

from tests.conftest import ACME


def me(client, headers) -> dict:
    return client.get("/auth/me", headers=headers).json()


def person(client, headers, email: str) -> dict:
    return next(u for u in client.get("/admin/users", headers=headers).json() if u["email"] == email)


def companies(client, headers) -> dict:
    return client.get("/auth/orgs", headers=headers).json()


def open_company(client, headers, org_id: str):
    return client.post("/auth/switch-org", json={"orgId": org_id}, headers=headers)


def getmeds(client, headers) -> str:
    return next(o["id"] for o in companies(client, headers)["items"] if o["slug"] == "getmeds")


def inside_getmeds(client, headers) -> dict:
    """A Developer Admin signs in to the platform, in no company at all, so
    anything belonging to one is reached by opening it first."""
    opened = open_company(client, headers, getmeds(client, headers))
    assert opened.status_code == 200, opened.text
    return {"Authorization": f"Bearer {opened.json()['accessToken']}"}


# --- it is not a role ------------------------------------------------------------


def test_no_company_can_grant_the_tier(client, as_):
    """It is absent from the role list, so there is nothing for an Admin to give
    -- to anyone, themselves included."""
    roles = client.get("/admin/roles", headers=as_("carmen")).json()
    keys = [r["key"] for r in roles["roles"]]
    assert "developer_admin" not in keys
    assert keys[-1] == "admin"


def test_the_top_company_role_is_called_admin(client, as_):
    roles = client.get("/admin/roles", headers=as_("carmen")).json()
    assert next(r["name"] for r in roles["roles"] if r["key"] == "admin") == "Admin"


def test_an_admin_can_copy_the_name_but_not_the_reach(client, as_, acme):
    """They may make a role called anything and give it the recovery key -- that
    is a company's business. What they cannot make is a person who reaches
    another company."""
    carmen = as_("carmen")
    made = client.post("/admin/roles", json={"name": "Developer Admin", "description": "mine"}, headers=carmen)
    assert made.status_code == 201
    key = next(r["key"] for r in made.json()["roles"] if r["name"] == "Developer Admin")
    matrix = client.get("/admin/roles", headers=carmen).json()["permissions"]
    matrix[key] = {"settings": ["recover"]}
    assert client.put("/admin/permissions", json={"permissions": matrix}, headers=carmen).status_code == 200
    body = {"roleKey": key, "moduleKey": "*", "divisionCode": None, "subdivisionCode": None}
    assert client.post(
        f"/admin/users/{person(client, carmen, 'ben@pharmacrm.test')['id']}/assignments", json=body, headers=carmen
    ).status_code == 201

    ben = as_("ben")
    assert me(client, ben)["canRecover"] is True  # in Getmeds, which is theirs to decide
    assert me(client, ben)["isDeveloperAdmin"] is False
    assert companies(client, ben)["everyCompany"] is False
    assert open_company(client, ben, ACME).status_code == 404


# --- what the tier carries -------------------------------------------------------


def test_signing_in_lands_on_the_platform_and_in_no_company(client, as_):
    """The whole point of the tier. Landing them in whichever company came first
    is how you end up looking at one company's settings when your job is all of
    them."""
    jun = as_("jun")
    body = me(client, jun)
    assert body["org"] is None
    assert body["isDeveloperAdmin"] is True
    assert body["canRecover"] is True
    assert body["canManageSettings"] is False
    assert body["modules"] == []
    # nothing belonging to a company is reachable until one is opened, and it
    # says so rather than failing somewhere deeper
    refused = client.get("/admin/apps", headers=jun)
    assert refused.status_code == 409
    assert "Open a company first" in refused.json()["detail"]


def test_it_holds_the_tier_without_any_role(client, as_):
    jun = inside_getmeds(client, as_("jun"))
    body = me(client, jun)
    assert body["isDeveloperAdmin"] is True and body["canRecover"] is True
    assert body["canManageSettings"] is False
    # granted nothing in the company, so nothing of its business is behind it
    assert body["modules"] == []
    assert client.get("/sales/customers", headers=jun).status_code == 403


def test_it_reaches_the_recovery_screens(client, as_):
    jun = inside_getmeds(client, as_("jun"))
    for path in ("/admin/apps", "/admin/audit", "/admin/users", "/admin/company", "/admin/roles"):
        assert client.get(path, headers=jun).status_code == 200, path


def test_it_reaches_no_business_rules(client, as_):
    jun = inside_getmeds(client, as_("jun"))
    for path in ("/admin/lists", "/admin/pricing", "/admin/orders", "/admin/retention", "/admin/goals", "/admin/fields"):
        assert client.get(path, headers=jun).status_code == 403, path
    assert client.put("/admin/permissions", json={"permissions": {}}, headers=jun).status_code == 403
    assert client.post("/admin/roles", json={"name": "Mine", "description": ""}, headers=jun).status_code == 403


def test_it_puts_a_locked_out_person_back(client, as_):
    """The job it exists for."""
    carmen = as_("carmen")
    jun = inside_getmeds(client, as_("jun"))
    lorna = person(client, carmen, "lorna@pharmacrm.test")
    assert client.patch(f"/admin/users/{lorna['id']}", json={"isActive": False}, headers=jun).status_code == 200
    back = client.patch(f"/admin/users/{lorna['id']}", json={"isActive": True, "password": "letmeback1"}, headers=jun)
    assert back.status_code == 200
    assert client.post("/auth/login", json={"email": "lorna@pharmacrm.test", "password": "letmeback1"}).status_code == 200


def test_everything_it_does_is_written_down(client, as_):
    carmen = as_("carmen")
    jun = inside_getmeds(client, as_("jun"))
    lorna = person(client, carmen, "lorna@pharmacrm.test")
    client.patch(f"/admin/users/{lorna['id']}", json={"password": "somethingnew1"}, headers=jun)
    entries = client.get("/admin/audit", headers=jun).json()["items"]
    assert any(e["action"] == "person.updated" and e["actor"] == "jun@pharmacrm.test" for e in entries)


# --- every company ---------------------------------------------------------------


def test_it_sees_every_company_on_the_platform(client, as_, acme):
    body = companies(client, as_("jun"))
    assert body["everyCompany"] is True
    assert {o["slug"] for o in body["items"]} == {"getmeds", "acme"}
    # none of them is theirs: a Developer Admin works in no company, which is
    # why they are in nobody's People screen and reach every one anyway.
    assert {o["isMine"] for o in body["items"]} == {False}


def test_an_admin_sees_only_their_own(client, as_, acme):
    body = companies(client, as_("carmen"))
    assert body["everyCompany"] is False
    assert [o["slug"] for o in body["items"]] == ["getmeds"]


def test_it_opens_a_company_it_does_not_work_in(client, as_, acme):
    jun = as_("jun")
    opened = open_company(client, jun, ACME)
    assert opened.status_code == 200, opened.text
    there = {"Authorization": f"Bearer {opened.json()['accessToken']}"}

    body = me(client, there)
    assert body["org"]["slug"] == "acme"
    assert body["isDeveloperAdmin"] is True
    # the recovery screens, in a company they are not a member of
    assert client.get("/admin/apps", headers=there).status_code == 200
    assert client.get("/admin/users", headers=there).status_code == 200
    # and still nothing of its business
    assert client.get("/admin/pricing", headers=there).status_code == 403
    assert body["modules"] == []


def test_the_wall_still_stands_for_everyone_else(client, as_, acme):
    """An Admin offered another company's id is told the same thing as someone
    who guessed it: no such company."""
    assert open_company(client, as_("carmen"), ACME).status_code == 404


def test_it_sees_one_company_at_a_time(client, as_, acme):
    """Opening a company walls the session to it, so nothing of the one left
    behind comes along."""
    jun = as_("jun")
    here = inside_getmeds(client, jun)
    getmeds_people = {u["email"] for u in client.get("/admin/users", headers=here).json()}
    there = {"Authorization": f"Bearer {open_company(client, here, ACME).json()['accessToken']}"}
    acme_people = {u["email"] for u in client.get("/admin/users", headers=there).json()}

    assert "carmen@pharmacrm.test" in getmeds_people
    assert "olga@acme.test" in acme_people
    assert not (getmeds_people & acme_people)


def test_opening_a_company_ends_the_session_it_came_from(client, as_, acme):
    jun = as_("jun")
    assert client.get("/auth/me", headers=jun).status_code == 200
    open_company(client, jun, ACME)
    assert client.get("/auth/me", headers=jun).status_code == 401
