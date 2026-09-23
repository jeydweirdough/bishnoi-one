"""Settings -> Apps: the other applications this company reaches from Orbit.

Where the Orders app lives used to be an environment variable, so a second
application meant a developer and a redeploy. What matters here is that a System
Admin can point an app somewhere else, add one of their own and switch one off
without anybody touching code -- and that the built-in ones, whose permissions
are in code and granted to people, cannot be deleted out from under them.
"""


def apps(client, headers) -> list[dict]:
    return client.get("/admin/apps", headers=headers).json()["apps"]


def one(rows: list[dict], code: str) -> dict:
    return next(r for r in rows if r["code"] == code)


def test_a_company_starts_with_the_apps_orbit_ships_with(client, as_):
    rows = apps(client, as_("carmen"))
    orders = one(rows, "orders")
    assert orders["name"] == "Orders" and orders["isBuiltIn"] is True and orders["isActive"] is True


def test_only_someone_who_manages_settings_may_look_or_change(client, as_):
    lorna = as_("lorna")
    assert client.get("/admin/apps", headers=lorna).status_code == 403
    assert client.put("/admin/apps", json={"apps": []}, headers=lorna).status_code == 403


def test_pointing_an_app_somewhere_else_is_what_everyone_then_opens(client, as_):
    carmen, lorna = as_("carmen"), as_("lorna")
    rows = apps(client, carmen)
    body = {"apps": [{**r, "url": "https://orders.getmeds.ph"} if r["code"] == "orders" else r for r in rows]}
    saved = client.put("/admin/apps", json=body, headers=carmen)
    assert saved.status_code == 200
    assert one(saved.json()["apps"], "orders")["url"] == "https://orders.getmeds.ph"
    # and that is the address the app's own people are handed
    mine = client.get("/auth/me", headers=lorna).json()["modules"]
    assert next(m["url"] for m in mine if m["key"] == "orders") == "https://orders.getmeds.ph"


def test_an_address_must_be_a_whole_one(client, as_):
    carmen = as_("carmen")
    rows = apps(client, carmen)
    # "localhost:3000" is the easy mistake: a browser reads it as a path, not a host.
    body = {"apps": [{**r, "url": "localhost:3000"} if r["code"] == "orders" else r for r in rows]}
    assert client.put("/admin/apps", json=body, headers=carmen).status_code == 422
    assert one(apps(client, carmen), "orders")["url"] != "localhost:3000"


def test_a_trailing_slash_is_not_kept_so_links_never_double_up(client, as_):
    carmen = as_("carmen")
    rows = apps(client, carmen)
    body = {"apps": [{**r, "url": "https://orders.example.com/"} if r["code"] == "orders" else r for r in rows]}
    saved = client.put("/admin/apps", json=body, headers=carmen)
    assert one(saved.json()["apps"], "orders")["url"] == "https://orders.example.com"


def test_no_address_means_nobody_is_sent_anywhere(client, as_):
    carmen, lorna = as_("carmen"), as_("lorna")
    rows = apps(client, carmen)
    body = {"apps": [{**r, "url": ""} if r["code"] == "orders" else r for r in rows]}
    saved = client.put("/admin/apps", json=body, headers=carmen)
    orders = one(saved.json()["apps"], "orders")
    assert orders["url"] == "" and orders["isReady"] is False
    assert next(m["url"] for m in client.get("/auth/me", headers=lorna).json()["modules"] if m["key"] == "orders") is None


def test_a_company_adds_an_app_of_its_own_and_it_gets_a_code(client, as_):
    carmen = as_("carmen")
    rows = apps(client, carmen)
    body = {"apps": [*rows, {"name": "Warehouse", "url": "https://wh.example.com", "description": "Stock counts"}]}
    saved = client.put("/admin/apps", json=body, headers=carmen)
    assert saved.status_code == 200
    added = one(saved.json()["apps"], "warehouse")
    assert added["isBuiltIn"] is False and added["url"] == "https://wh.example.com"
    # it keeps that code, so a role granted against it stays granted
    again = {"apps": [{**r, "name": "Warehouse & stores"} if r["code"] == "warehouse" else r for r in apps(client, carmen)]}
    assert one(client.put("/admin/apps", json=again, headers=carmen).json()["apps"], "warehouse")["name"] == "Warehouse & stores"


def test_an_added_app_reaches_only_people_whose_role_was_given_it(client, as_):
    """The same rule as a department the company adds: the link exists, but a
    module nobody has been granted is in nobody's sidebar."""
    carmen, lorna = as_("carmen"), as_("lorna")
    rows = apps(client, carmen)
    client.put("/admin/apps", json={"apps": [*rows, {"name": "Warehouse", "url": "https://wh.example.com"}]}, headers=carmen)
    assert "warehouse" not in [m["key"] for m in client.get("/auth/me", headers=lorna).json()["modules"]]


def test_two_apps_cannot_share_a_name(client, as_):
    carmen = as_("carmen")
    rows = apps(client, carmen)
    body = {"apps": [*rows, {"name": "Orders", "url": "https://other.example.com"}]}
    assert client.put("/admin/apps", json=body, headers=carmen).status_code == 422


def test_an_app_of_ones_own_can_be_removed(client, as_):
    carmen = as_("carmen")
    rows = apps(client, carmen)
    client.put("/admin/apps", json={"apps": [*rows, {"name": "Warehouse"}]}, headers=carmen)
    left = [r for r in apps(client, carmen) if r["code"] != "warehouse"]
    saved = client.put("/admin/apps", json={"apps": left}, headers=carmen)
    assert "warehouse" not in [r["code"] for r in saved.json()["apps"]]


def test_a_built_in_app_left_out_is_kept_rather_than_deleted(client, as_):
    """Its order steps are in code and granted to people; deleting the row would
    leave those grants pointing at nothing."""
    carmen = as_("carmen")
    saved = client.put("/admin/apps", json={"apps": []}, headers=carmen)
    assert saved.status_code == 200
    assert [r["code"] for r in saved.json()["apps"]] == ["orders"]
    assert one(saved.json()["apps"], "orders")["isBuiltIn"] is True


def test_switching_one_off_sends_nobody_there_but_keeps_the_grants(client, as_):
    """A company that stops using an application switches it off. The link goes
    from every sidebar at once; the order steps stay in Roles, so nothing that
    was granted is quietly thrown away."""
    carmen, lorna = as_("carmen"), as_("lorna")
    rows = apps(client, carmen)
    live = [{**r, "url": "https://orders.example.com"} if r["code"] == "orders" else r for r in rows]
    client.put("/admin/apps", json={"apps": live}, headers=carmen)
    off = [{**r, "isActive": False} if r["code"] == "orders" else r for r in live]
    saved = client.put("/admin/apps", json={"apps": off}, headers=carmen)

    orders = one(saved.json()["apps"], "orders")
    assert orders["isActive"] is False
    # it is remembered whole: the name and the address are still there to come back to
    assert orders["name"] == "Orders" and orders["url"] == "https://orders.example.com"
    mine = client.get("/auth/me", headers=lorna).json()["modules"]
    assert next(m["url"] for m in mine if m["key"] == "orders") is None
    assert "orders" in [m["key"] for m in mine]


def test_renaming_the_orders_app_renames_it_everywhere(client, as_):
    carmen, lorna = as_("carmen"), as_("lorna")
    rows = apps(client, carmen)
    body = {"apps": [{**r, "name": "Sales orders"} if r["code"] == "orders" else r for r in rows]}
    assert client.put("/admin/apps", json=body, headers=carmen).status_code == 200
    mine = client.get("/auth/me", headers=lorna).json()["modules"]
    assert next(m["name"] for m in mine if m["key"] == "orders") == "Sales orders"


def test_the_change_is_written_down(client, as_):
    carmen = as_("carmen")
    rows = apps(client, carmen)
    client.put("/admin/apps", json={"apps": rows}, headers=carmen)
    entries = client.get("/admin/audit", headers=carmen).json()["items"]
    assert any(e["action"] == "apps.changed" for e in entries)
