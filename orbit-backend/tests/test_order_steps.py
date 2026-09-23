"""Order steps live in Orbit's roles; the Orders app asks Orbit who may take which step."""

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, select

from app.access import resolve
from app.config import API_DIR
from app.db import make_engine
from app.modules import ORDER_ACTIONS, ORDER_HOMES, ORDERS, valid_grant
from app.scope import Scope
from app.tenancy import FIRST_ORG_ID

TEAMS = {"bnb": ["general", "md-telesales"], "b2c": ["general"], "bid": ["general"], "finance": ["general"]}
MATRIX = {
    "rep": {"bnb": {"view", "create", "edit"}, ORDERS: {"view", "raise"}},
    "management": {ORDERS: {"view", "approve"}},
    "clerk": {"finance": {"view"}},
}


class A:
    def __init__(self, role, module, division=None, team=None):
        self.role_key, self.module_key, self.division_code, self.subdivision_code = role, module, division, team


def test_a_sales_team_assignment_carries_the_roles_order_steps_for_that_team():
    access = resolve([A("rep", "bnb", "bnb", "md-telesales")], MATRIX, TEAMS)
    assert access.scopes(ORDERS, "raise") == {Scope("bnb", "md-telesales")}
    assert access.scopes(ORDERS, "view") == {Scope("bnb", "md-telesales")}
    assert not access.can(ORDERS, "approve")


def test_an_orders_assignment_reaches_every_division_orders_are_raised_in_and_no_other():
    access = resolve([A("management", ORDERS)], MATRIX, TEAMS)
    reached = {s.division for s in access.scopes(ORDERS, "approve")}
    assert reached == {"bnb", "b2c", "bid"}
    assert reached <= set(ORDER_HOMES)


def test_a_department_assignment_carries_no_order_steps():
    access = resolve([A("clerk", "finance")], MATRIX, TEAMS)
    assert not access.can(ORDERS, "view")


def test_order_steps_are_only_valid_in_orders():
    assert all(valid_grant(ORDERS, a) for a in ORDER_ACTIONS)
    assert not valid_grant(ORDERS, "report") and not valid_grant(ORDERS, "create")
    assert not valid_grant("bnb", "approve") and not valid_grant("finance", "verify_payment")


def test_the_role_screen_gets_the_order_steps_grouped(client, as_):
    data = client.get("/admin/roles", headers=as_("carmen")).json()
    groups = [g["group"] for g in data["orderSteps"]]
    assert groups == ["Raise and edit", "Approvals", "Finance", "Fulfilment", "Admin"]
    orders = next(m for m in data["modules"] if m["key"] == ORDERS)
    assert orders["kind"] == "app" and orders["actions"] == list(ORDER_ACTIONS)
    assert data["permissions"]["management"][ORDERS] == ["view", "edit", "approve", "send_back", "reject"]
    assert {"finance_staff", "dispatch_staff", "management"} <= {r["key"] for r in data["roles"]}


def test_admins_can_grant_order_steps_but_not_nonsense(client, as_):
    carmen = as_("carmen")
    ok = client.put("/admin/permissions", json={"permissions": {"rep": {ORDERS: ["view", "raise", "edit"], "bnb": ["view"]}}}, headers=carmen)
    assert ok.status_code == 200, ok.text
    bad = client.put("/admin/permissions", json={"permissions": {"rep": {ORDERS: ["view", "report"]}}}, headers=carmen)
    assert bad.status_code == 422


def test_orders_is_assigned_to_order_divisions_only(client, as_):
    carmen = as_("carmen")
    joy = next(u["id"] for u in client.get("/admin/users", headers=carmen).json() if u["email"] == "joy@pharmacrm.test")
    to = lambda division: {"roleKey": "finance_staff", "moduleKey": ORDERS, "divisionCode": division}  # noqa: E731
    assert client.post(f"/admin/users/{joy}/assignments", json=to("finance"), headers=carmen).status_code == 422
    assert client.post(f"/admin/users/{joy}/assignments", json=to(None), headers=carmen).status_code == 201
    me = client.post("/auth/login", json={"email": "joy@pharmacrm.test", "password": "demo1234"}).json()
    modules = {m["key"]: m for m in client.get("/auth/me", headers={"Authorization": f"Bearer {me['accessToken']}"}).json()["modules"]}
    assert modules[ORDERS]["actions"] == ["view", "edit", "verify_payment", "hold"]


def test_orders_is_not_a_division(client, as_):
    tree = client.get("/org", headers=as_("carmen")).json()
    assert ORDERS not in {d["code"] for d in tree["divisions"]}


def test_existing_companies_get_order_steps_on_upgrade(tmp_path):
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    config = Config(str(API_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    config.attributes["configure_logger"] = False
    command.upgrade(config, "0005")
    engine = make_engine(url)
    with engine.begin() as connection:
        meta = MetaData()
        roles = Table("roles", meta, autoload_with=connection)  # 0005 made Getmeds, company #1
        connection.execute(roles.insert(), [
            {"org_id": FIRST_ORG_ID, "key": "rep", "name": "Rep", "description": "", "sort_order": 0},
            {"org_id": FIRST_ORG_ID, "key": "management", "name": "Our own Management", "description": "", "sort_order": 1},
        ])
    command.upgrade(config, "head")
    with engine.connect() as connection:
        meta = MetaData()
        perms = Table("role_permissions", meta, autoload_with=connection)
        roles = Table("roles", meta, autoload_with=connection)
        grants = set(connection.execute(select(perms.c.role_key, perms.c.module_key, perms.c.action)).all())
        names = dict(connection.execute(select(roles.c.key, roles.c.name)).all())
    assert {("rep", ORDERS, "view"), ("rep", ORDERS, "raise")} <= grants
    assert names["management"] == "Our own Management"  # an existing role is left alone
    assert not any(r == "management" for r, _, _ in grants)
    assert {"finance_staff", "dispatch_staff"} <= set(names)
    assert ("dispatch_staff", ORDERS, "fulfil") in grants
