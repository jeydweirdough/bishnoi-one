"""An Inventory API on a fresh database for each test, with one person per
starting role: Ana (Administrator), Wes (Warehouse), Pia (Purchasing),
Sal (Sales) and Aud (Auditor)."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.config import Settings
from app.db import make_engine
from app.main import create_app
from app.models import Role, User
from app.routers.auth import attempts
from app.security import hash_password

PASSWORD = "correct horse battery"
PEOPLE = {
    "ana": "Administrator",
    "wes": "Warehouse",
    "pia": "Purchasing",
    "sal": "Sales",
    "aud": "Auditor",
}

# TEST_DATABASE_URL runs every test on that Postgres database instead, emptied
# before each one (so never point it at a database that matters).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def fresh_database(tmp_path) -> str:
    if not TEST_DATABASE_URL:
        return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = make_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    return TEST_DATABASE_URL


def settings_for(tmp_path, **extra) -> Settings:
    return Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path), **extra)


@pytest.fixture
def app(tmp_path):
    attempts.clear()
    app = create_app(settings_for(tmp_path))
    with app.state.sessions() as db:
        for name, role in PEOPLE.items():
            role_id = db.scalar(select(Role.id).where(Role.name == role))
            db.add(User(email=f"{name}@example.com", full_name=name.title(), password_hash=hash_password(PASSWORD), role_id=role_id))
        db.commit()
    yield app
    # Let go of its connections, so the next test can empty the database.
    app.state.sessions.kw["bind"].dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def sign_in(client, email="ana@example.com", password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def bearer(r) -> dict:
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


@pytest.fixture
def people(client) -> dict[str, dict]:
    """Each person's sign-in headers, by name."""
    return {name: bearer(sign_in(client, f"{name}@example.com")) for name in PEOPLE}


class Api:
    """The client, signed in as someone, failing loudly on anything unexpected."""

    def __init__(self, client, headers):
        self.c, self.h = client, headers

    def get(self, path, **params):
        r = self.c.get(path, headers=self.h, params=params)
        assert r.status_code == 200, r.text
        return r.json()

    def post(self, path, body=None, expect=(200, 201)):
        r = self.c.post(path, headers=self.h, json=body or {})
        assert r.status_code in (expect if isinstance(expect, tuple) else (expect,)), r.text
        return r.json() if r.content else None

    def put(self, path, body, expect=200):
        r = self.c.put(path, headers=self.h, json=body)
        assert r.status_code == expect, r.text
        return r.json()

    def patch(self, path, body, expect=200):
        r = self.c.patch(path, headers=self.h, json=body)
        assert r.status_code == expect, r.text
        return r.json()


@pytest.fixture
def ana(client, people) -> Api:
    return Api(client, people["ana"])


@pytest.fixture
def world(ana) -> dict:
    """Two warehouses, a supplier, and three products: one plain, one by batch
    and expiry, one by serial number."""
    mnl = ana.post("/inventory/warehouses", {"code": "MNL", "name": "Manila"})["id"]
    ceb = ana.post("/inventory/warehouses", {"code": "CEB", "name": "Cebu"})["id"]
    supplier = ana.post("/inventory/suppliers", {"code": "ABC", "name": "ABC Medical Supply", "leadTimeDays": 5})["id"]
    gloves = ana.post("/inventory/products", {"sku": "GLV-M", "name": "Gloves M", "unitCode": "box", "costPrice": 18500, "sellingPrice": 32000, "reorderPoint": 50, "supplierId": supplier})["id"]
    pcm = ana.post("/inventory/products", {"sku": "PCM-500", "name": "Paracetamol 500mg", "unitCode": "box", "costPrice": 9500, "reorderPoint": 10, "trackBatches": True, "trackExpiry": True})["id"]
    pump = ana.post("/inventory/products", {"sku": "PUMP", "name": "Infusion pump", "costPrice": 4800000, "trackSerials": True})["id"]
    return {"mnl": mnl, "ceb": ceb, "supplier": supplier, "gloves": gloves, "pcm": pcm, "pump": pump}


def receive(api: Api, warehouse: str, lines: list[dict], **extra) -> dict:
    return api.post("/inventory/receipts", {"warehouseId": warehouse, "lines": lines, **extra})


def level(api: Api, product: str, warehouse: str | None = None) -> dict:
    p = api.get(f"/inventory/products/{product}")
    if warehouse is None:
        return p["level"]
    return next((w for w in p["warehouses"] if w["warehouse"]["id"] == warehouse), {"onHand": 0, "available": 0, "reserved": 0, "allocated": 0, "inTransit": 0, "damaged": 0})
