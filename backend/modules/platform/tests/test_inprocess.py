"""Stage M2 (2026-11-18): modules of the one backend call each other in-process (modules/inprocess.py),
without connection keys; a request from outside is never taken for a module's.

Real module apps (Platform, Inventory) on fresh SQLite databases, registered the way backend/main.py
registers them, and the CRM's and Finance's own calling code, with no key set anywhere."""

import base64
import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select

from modules import inprocess
from modules.dispatch import Modules
from modules.platform import addresses, events
from modules.platform.config import Settings as PlatformSettings
from modules.platform.main import create_app as platform_app
from modules.platform.models import User
from modules.platform.security import hash_password
from modules.platform.tests.conftest import PASSWORD, bearer, make_company, sign_in

BASE = "http://127.0.0.1:8300"
HOSTS = ["testserver", "127.0.0.1"]


@pytest.fixture
def inventory(tmp_path):
    """Inventory, with two products, registered at /inventory; no integration keys at all."""
    from modules.inventory.config import Settings
    from modules.inventory.main import create_app
    from modules.inventory.models import Role, User as InventoryUser
    from modules.inventory.security import hash_password as inventory_hash

    (tmp_path / "inventory").mkdir()
    app = create_app(Settings(_env_file=None, allowed_hosts=HOSTS, database_url=f"sqlite:///{(tmp_path / 'inventory' / 'test.db').as_posix()}"))
    with app.state.sessions() as db:
        role_id = db.scalar(select(Role.id).where(Role.name == "Administrator"))
        db.add(InventoryUser(email="ana@example.com", full_name="Ana", password_hash=inventory_hash(PASSWORD), role_id=role_id))
        db.commit()
    with TestClient(app) as c:
        ana = bearer(c.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}))
        for sku, cost in (("GLV-M", 18500), ("PCM-500", 9500)):
            r = c.post("/inventory/products", headers=ana, json={"sku": sku, "name": sku, "unitCode": "box", "costPrice": cost, "sellingPrice": cost * 2})
            assert r.status_code in (200, 201), r.text
    inprocess.register(BASE, "inventory", "/inventory", app)
    yield app
    inprocess.clear()
    app.state.tenants.close()


def test_the_crm_reads_inventorys_products_in_process_without_a_key(inventory, tmp_path):
    from modules.crm import inventory as crm_inventory
    from modules.crm.config import Settings

    crm = Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path / 'crm.db').as_posix()}", inventory_api_url=f"{BASE}/inventory")
    assert crm.inventory_api_key is None and crm.inventory_linked  # linked: the address alone, in the one backend
    skus = [p["sku"] for p in crm_inventory.call(crm, "products")["items"]]
    assert skus == ["GLV-M", "PCM-500"]
    # Without the one backend (a module's own tests, a module alone) a link still needs its key.
    inprocess.clear()
    assert not crm.inventory_linked


def test_finance_reads_what_each_product_costs_in_process(inventory, tmp_path):
    from modules.finance import inventory as finance_inventory
    from modules.finance.config import Settings

    finance = Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path / 'finance.db').as_posix()}", inventory_api_url=f"{BASE}/inventory")
    assert finance.inventory_linked
    assert finance_inventory.unit_costs(finance, ["glv-m", "PCM-500", "NOPE"]) == {"GLV-M": 18500, "PCM-500": 9500}


def test_a_call_from_inside_a_running_request_sync_or_async(inventory):
    """A route of one module calling another (the usual case) never waits on the loop serving it."""
    probe = FastAPI()

    @probe.get("/sync")
    def sync_route() -> dict:
        return inprocess.get("crm", f"{BASE}/inventory/integration/products").json()

    @probe.get("/async")
    async def async_route() -> dict:
        return inprocess.get("crm", f"{BASE}/inventory/integration/costs", params={"skus": "GLV-M"}).json()

    with TestClient(probe) as c:
        assert len(c.get("/sync").json()["items"]) == 2
        assert c.get("/async").json()["items"]["GLV-M"]["unitCost"] == 18500


def test_a_request_from_outside_is_never_taken_for_a_module(inventory):
    """Through the backend's front door, neither a header nor a scope key makes a request a module's."""
    front = Modules(FastAPI(), [("/inventory", inventory)])

    async def planted(scope, receive, send):  # as if something in front had set the mark itself
        await front({**scope, inprocess.MARK: "crm"}, receive, send)

    with TestClient(front, base_url=BASE) as c:
        assert c.get("/inventory/integration/products", headers={inprocess.MARK: "crm", "X-Bishnoi-Internal": "crm"}).status_code == 401
    with TestClient(planted, base_url=BASE) as c:
        assert c.get("/inventory/integration/products").status_code == 401
    # In-process, the same request is the CRM's.
    assert inprocess.get("crm", f"{BASE}/inventory/integration/products").status_code == 200
    # An address outside the one backend isn't served in-process.
    assert not inprocess.serves("https://inventory-api.example.com/integration/products")
    assert not inprocess.serves(f"{BASE}/nothing-here/x")


def test_an_event_is_taken_and_delivered_in_process(tmp_path, monkeypatch):
    """Finance sends an event to the Platform with no connect key; the Platform delivers it, signed,
    to the CRM in-process."""
    (tmp_path / "platform").mkdir()
    settings = PlatformSettings(_env_file=None, allowed_hosts=HOSTS, backend_url=BASE,
                                database_url=f"sqlite:///{(tmp_path / 'platform' / 'test.db').as_posix()}")
    platform = platform_app(settings)
    with platform.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role="admin"))
        db.commit()
    monkeypatch.setattr(events, "kick", lambda sessions, s: _deliver(sessions, s))

    heard: list[tuple[str | None, dict]] = []
    crm = FastAPI()

    @crm.post("/platform/events")
    async def take(request: Request) -> dict:
        heard.append((inprocess.caller(request), await request.json()))
        return {"ok": True}

    try:
        with TestClient(platform) as c:
            company = make_company(c, bearer(sign_in(c)), apps=("crm", "finance"))
        inprocess.register(BASE, "platform", "/platform", platform)
        inprocess.register(BASE, "crm", "/crm", crm)
        body = {"company": company["slug"], "events": [{"id": "ev-m2-0001", "kind": "invoice.issued", "data": {"number": "INV-1"}, "occurredAt": "2026-11-18T08:00:00+00:00"}]}
        # Not from outside without a key...
        with TestClient(platform) as c:
            assert c.post("/connect/events", json=body).status_code == 401
        # ...but from Finance in-process.
        r = inprocess.post("finance", f"{BASE}/platform/connect/events", json=body, timeout=10)
        assert r.status_code == 200 and r.json()["taken"] == ["ev-m2-0001"]
        assert len(heard) == 1
        who, sent = heard[0]
        assert who == "platform"
        claims = _claims(sent["pass"])
        assert claims["aud"] == "crm" and claims["event"]["id"] == "ev-m2-0001" and claims["event"]["source"] == "finance"
        # The Connections data says the two are linked without keys.
        with TestClient(platform) as c:
            listed = c.get("/platform/connections", headers=bearer(sign_in(c))).json()
        assert {a["key"]: a["inBackend"] for a in listed["applications"]}["crm"] is True
    finally:
        inprocess.clear()
        addresses.configure(None)
        platform.state.sessions.kw["bind"].dispose()


def _deliver(sessions, settings):
    with sessions() as db:
        events.deliver_due(db, settings)


def _claims(token: str) -> dict:
    body = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
