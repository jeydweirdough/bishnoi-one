"""The product list and stock come from Bishnoi One Inventory, when it's linked:
here Inventory is a stand-in answering as the real one does."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import inventory
from app.config import Settings
from app.main import create_app
from app.models import SalesSettings, User
from app.routers.auth import attempts
from app.security import hash_password
from tests.conftest import PASSWORD, bearer, fresh_database, role_id, sign_in


def item(sku, name, price, status="active", **extra):
    return {"id": f"inv-{sku}", "sku": sku, "name": name, "unit": {"code": "box", "name": "box"}, "status": status,
            "productType": "stock", "sellingPrice": price, "attributes": extra.pop("attributes", {}), **extra}


class FakeInventory:
    def __init__(self):
        self.products = [item("amx-500", "Amoxicillin 500mg", 25000, attributes={"Generic name": "Amoxicillin"}), item("GLV-M", "Gloves M", 32000)]
        self.levels = {"AMX-500": {"sku": "amx-500", "state": "low", "available": 4, "onHand": 4, "inTransit": 0,
                                   "warehouses": [{"id": "w1", "code": "MNL", "name": "Manila", "available": 4, "onHand": 4, "inTransit": 0}]}}
        self.down = False
        self.stock_calls = 0

    def __call__(self, settings, path, params=None):
        if self.down:
            raise inventory.Unreachable("Inventory can't be reached right now.")
        if path == "products":
            return {"items": self.products}
        self.stock_calls += 1
        return {"items": [self.levels[s.upper()] for s in params["skus"].split(",") if s.upper() in self.levels]}


@pytest.fixture
def fake(monkeypatch):
    f = FakeInventory()
    monkeypatch.setattr(inventory, "call", f)
    inventory._stock.clear()
    return f


@pytest.fixture
def app(tmp_path, fake):
    attempts.clear()
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path), files_dir=tmp_path / "files",
                        inventory_api_url="http://inventory.test", inventory_api_key="k" * 32)
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Administrator")))
        db.commit()
    yield app
    app.state.sessions.kw["bind"].dispose()


@pytest.fixture
def ana(client: TestClient) -> dict:
    return bearer(sign_in(client))


def products(client, ana) -> dict:
    return {p["code"]: p for p in client.get("/products", headers=ana).json()["items"]}


def test_the_list_comes_over_with_the_srp(client, ana, fake):
    body = client.get("/products", headers=ana).json()
    assert body["inventory"]["linked"] and body["inventory"]["syncedAt"] and body["inventory"]["error"] is None
    listed = {p["code"]: p for p in body["items"]}
    assert set(listed) == {"AMX-500", "GLV-M"}
    amx = listed["AMX-500"]
    assert amx["fromInventory"] and amx["prices"]["SRP"] == 25000 and amx["unit"] == "box" and amx["genericName"] == "Amoxicillin"
    # The SRP is a price type like any other: teams can quote their own over it.
    assert "SRP" in [t["code"] for t in client.get("/pricing", headers=ana).json()["priceTypes"]]


def test_changes_in_inventory_follow_and_gone_ones_switch_off(client, ana, fake):
    products(client, ana)
    fake.products = [item("amx-500", "Amoxicillin 500 mg caps", 26000), item("GLV-M", "Gloves M", 32000, status="discontinued"), item("NEW-1", "Syringe 3 mL", 1500)]
    assert client.post("/products/sync", headers=ana).json()["added"] == 1
    listed = products(client, ana)
    assert listed["AMX-500"]["name"] == "Amoxicillin 500 mg caps" and listed["AMX-500"]["prices"]["SRP"] == 26000
    assert listed["AMX-500"]["genericName"] == "Amoxicillin"  # Inventory has none now: kept
    assert listed["GLV-M"]["isActive"] is False
    fake.products = fake.products[:1]
    client.post("/products/sync", headers=ana)
    assert products(client, ana)["NEW-1"]["isActive"] is False


def test_a_product_made_here_first_is_matched_by_code(client, ana, fake, app):
    with app.state.sessions() as db:
        db.get(SalesSettings, 1).inventory_synced_at = None
        db.commit()
    # Made before the link (no Inventory then): the sync takes it over, not a copy.
    from app.models import Product

    with app.state.sessions() as db:
        db.add(Product(code="GLV-M", name="Gloves (old name)"))
        db.commit()
    client.post("/products/sync", headers=ana)
    with app.state.sessions() as db:
        gloves = db.scalars(select(Product).where(Product.code == "GLV-M")).all()
    assert len(gloves) == 1 and gloves[0].name == "Gloves M" and gloves[0].inventory_id == "inv-GLV-M"


def test_inventorys_fields_are_changed_there(client, ana, fake):
    amx = products(client, ana)["AMX-500"]
    assert client.post("/products", json={"code": "X-1", "name": "Made here"}, headers=ana).status_code == 409
    r = client.patch(f"/products/{amx['id']}", json={"name": "Renamed"}, headers=ana)
    assert r.status_code == 422 and "Inventory" in r.text
    assert client.patch(f"/products/{amx['id']}", json={"prices": {"SRP": 1}}, headers=ana).status_code == 422
    assert client.delete(f"/products/{amx['id']}", headers=ana).status_code == 409
    # What's the CRM's own stays editable.
    assert client.patch(f"/products/{amx['id']}", json={"strength": "500 mg"}, headers=ana).json()["strength"] == "500 mg"


def test_stock_is_asked_for_live_and_kept_a_minute(client, ana, fake):
    products(client, ana)
    r = client.get("/stock", params={"codes": "AMX-500,GLV-M,NOT-THERE"}, headers=ana).json()
    assert r["linked"] and r["error"] is None
    assert r["items"]["AMX-500"]["available"] == 4 and r["items"]["AMX-500"]["warehouses"][0]["name"] == "Manila"
    assert r["items"]["GLV-M"] is None and "NOT-THERE" not in r["items"]
    client.get("/stock", params={"codes": "AMX-500"}, headers=ana)
    assert fake.stock_calls == 1


def test_inventory_down_never_breaks_the_page(client, ana, fake):
    fake.down = True
    body = client.get("/products", headers=ana).json()
    assert body["items"] == [] and "can't be reached" in body["inventory"]["error"]
    assert client.post("/products/sync", headers=ana).status_code == 502
    fake.down = False
    client.post("/products/sync", headers=ana)
    inventory._stock.clear()
    fake.down = True
    r = client.get("/stock", params={"codes": "AMX-500"}, headers=ana).json()
    assert r["items"] == {} and r["error"]


def test_an_import_only_changes_what_is_the_crms(client, ana, fake):
    products(client, ana)
    # code, name, strength, SRP
    rows = [["AMX-500", "Amoxicillin 500mg", "500 mg", "250.00"], ["AMX-500B", "Made up", "", ""], ["GLV-M", "Gloves M", "", "400.00"]]
    mapping = {"code": 0, "name": 1, "strength": 2, "price:SRP": 3}
    done = client.post("/imports/products", json={"mapping": mapping, "rows": rows, "dryRun": False}, headers=ana).json()
    assert done["updated"] == 1 and done["added"] == 0
    assert [(p["row"], "Inventory" in p["message"]) for p in done["problems"]] == [(3, True), (4, True)]
    assert products(client, ana)["AMX-500"]["strength"] == "500 mg"
