"""Each company's data in a database of its own (app/tenants.py): nothing one
company keeps is seen by another, and a session opens its own company only."""

from sqlalchemy import select

from app.models import Role, User
from app.security import hash_password
from app.tenants import database_url, slug_of_token
from tests.conftest import PASSWORD, bearer, sign_in

NORTHWIND = {"X-Bishnoi-Company": "northwind"}


def test_where_each_company_is_kept():
    assert database_url("sqlite:///.data/inventory.db", "getmeds") == "sqlite:///.data/inventory-getmeds.db"
    assert database_url("postgresql+psycopg://u:p@host/neondb?sslmode=require", "north-wind") == "postgresql+psycopg://u:p@host/neondb_north_wind?sslmode=require"
    assert slug_of_token("getmeds.abc") == "getmeds" and slug_of_token("abc") is None


def test_companies_keep_apart(app, client):
    ana = bearer(sign_in(client))
    assert ana["Authorization"].startswith("Bearer getmeds.")
    with app.state.tenants.get("northwind").sessions() as db:
        assert db.query(User).count() == 0
        admin = db.scalar(select(Role.id).where(Role.name == "Administrator"))
        db.add(User(email="nia@northwind.test", full_name="Nia Santos", password_hash=hash_password(PASSWORD), role_id=admin))
        db.commit()
    # Ana is GetMeds's: not an account at Northwind.
    assert client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}, headers=NORTHWIND).status_code == 401
    nia = bearer(client.post("/auth/login", json={"email": "nia@northwind.test", "password": PASSWORD}, headers=NORTHWIND))

    made = client.post("/inventory/warehouses", headers=ana, json={"code": "QC", "name": "Quezon City"})
    assert made.status_code == 201, made.text
    codes = lambda who: [w["code"] for w in client.get("/inventory/warehouses", headers=who).json()]  # noqa: E731
    assert "QC" in codes(ana) and "QC" not in codes(nia)
    # One company's token, given another company's name, isn't a session there.
    forged = {"Authorization": "Bearer northwind." + ana["Authorization"].split(".", 1)[1]}
    assert client.get("/inventory/warehouses", headers=forged).status_code == 401


def test_on_this_computer_only_the_dev_companies(client):
    r = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}, headers={"X-Bishnoi-Company": "nowhere"})
    assert r.status_code == 403 and "no company" in r.json()["detail"]
    assert client.get("/auth/company").json()["slug"] == "getmeds"
