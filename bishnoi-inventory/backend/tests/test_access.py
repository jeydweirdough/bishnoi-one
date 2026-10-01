"""Who may do what: the starting roles, and administering them."""

from sqlalchemy import text

from app.db import make_engine
from app.main import create_app
from app.models import User
from tests.conftest import Api, receive, settings_for


def status(client, headers, method, path, body=None):
    return client.request(method, path, headers=headers, json=body).status_code


def test_the_starting_roles_match_the_table(client, people, ana, world):
    """View / Receive / Adjust / Transfer / Approve, per role."""
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 100}])
    receipt = {"warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": 1}]}
    adjust = {"warehouseId": world["mnl"], "reason": "found", "lines": [{"productId": world["gloves"], "quantity": 1}]}
    transfer = {"fromWarehouseId": world["mnl"], "toWarehouseId": world["ceb"], "lines": [{"productId": world["gloves"], "quantity": 1}]}
    expected = {
        #      view receive adjust transfer approve-adjustment
        "wes": (200, 201, 201, 201, 403),
        "pia": (200, 201, 403, 403, 200),
        "sal": (200, 403, 403, 403, 403),
        "aud": (200, 403, 403, 403, 403),
    }
    for name, want in expected.items():
        h = people[name]
        pending = Api(client, people["wes"]).post("/inventory/adjustments", adjust)["id"]
        got = (
            status(client, h, "GET", "/inventory/stock"),
            status(client, h, "POST", "/inventory/receipts", receipt),
            status(client, h, "POST", "/inventory/adjustments", adjust),
            status(client, h, "POST", "/inventory/transfers", transfer),
            status(client, h, "POST", f"/inventory/adjustments/{pending}/approve"),
        )
        assert got == want, name


def test_only_admins_reach_administration(client, people):
    assert status(client, people["ana"], "GET", "/admin/users") == 200
    assert status(client, people["wes"], "GET", "/admin/users") == 403
    # The auditor reads the activity log, and nothing else of administration.
    assert status(client, people["aud"], "GET", "/admin/audit") == 200
    assert status(client, people["aud"], "GET", "/admin/roles") == 403


def test_a_role_can_be_made_and_given(client, people, ana):
    role = ana.post("/admin/roles", {"name": "Counter", "permissions": ["stock.view", "counts.view", "counts.create"]})
    wes = next(u for u in ana.get("/admin/users")["items"] if u["email"] == "wes@example.com")
    ana.patch(f"/admin/users/{wes['id']}", {"roleId": role["id"]})
    me = client.get("/auth/me", headers=people["wes"]).json()
    assert me["role"]["name"] == "Counter" and me["permissions"] == ["counts.create", "counts.view", "stock.view"]
    log = ana.get("/admin/audit")["items"]
    assert [e["action"] for e in log[:2]] == ["user.updated", "role.created"]


def test_nobody_can_lock_everyone_out(client, people, ana):
    me = next(u for u in ana.get("/admin/users")["items"] if u["email"] == "ana@example.com")
    warehouse = next(r for r in ana.get("/admin/roles")["roles"] if r["name"] == "Warehouse")
    r = client.patch(f"/admin/users/{me['id']}", headers=people["ana"], json={"roleId": warehouse["id"]})
    assert r.status_code == 409


def test_accounts_from_before_migrations_carry_over(tmp_path):
    """The first inventory had plain users/sessions tables; its people keep their accounts."""
    settings = settings_for(tmp_path)
    engine = make_engine(settings.database_url)
    with engine.begin() as c:
        c.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(254), full_name VARCHAR(120), password_hash VARCHAR(255), role VARCHAR(16), is_active BOOLEAN, created_at DATETIME, password_changed_at DATETIME)"))
        c.execute(text("CREATE TABLE sessions (id VARCHAR(36) PRIMARY KEY, token_hash VARCHAR(64), user_id VARCHAR(36), created_at DATETIME, expires_at DATETIME, revoked_at DATETIME)"))
        c.execute(text("INSERT INTO users VALUES ('u1', 'old@example.com', 'Old Admin', 'x', 'admin', 1, '2026-01-01 00:00:00', '2026-01-01 00:00:00')"))
        c.execute(text("INSERT INTO users VALUES ('u2', 'staff@example.com', 'Old Staff', 'x', 'member', 1, '2026-01-01 00:00:00', '2026-01-01 00:00:00')"))
    engine.dispose()
    app = create_app(settings)
    with app.state.sessions() as db:
        people = {u.email: u.role.name for u in db.query(User)}
        tables = set(db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
    assert people == {"old@example.com": "Administrator", "staff@example.com": "Warehouse"}
    assert "users" not in tables and "nbin_users" in tables
    assert all(t.startswith("nbin_") for t in tables)
    app.state.sessions.kw["bind"].dispose()
