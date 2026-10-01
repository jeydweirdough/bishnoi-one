"""Finance reads the CRM's customers to invoice them, with its key only."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import bearer, fresh_database, sign_in
from tests.test_customers import company

KEY = "finance-key-that-is-long-enough-1234"


@pytest.fixture
def client(tmp_path):
    from sqlalchemy import select

    from app.models import Role, User
    from app.security import hash_password

    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path), files_dir=tmp_path / "files", integration_keys=[f"finance:{KEY}"])
    app = create_app(settings)
    with app.state.sessions() as db:
        admin = db.scalar(select(Role.id).where(Role.name == "Administrator"))
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password("correct horse battery"), role_id=admin))
        db.commit()
    with TestClient(app) as c:
        yield c
    app.state.sessions.kw["bind"].dispose()


def test_finance_finds_customers_with_its_key(client):
    ana = bearer(sign_in(client))
    made = company(client, ana, name="Mercury Drug Makati", address="Ayala Ave", city="Makati", email="buy@mercury.test")
    company(client, ana, name="Watsons BGC")
    assert client.get("/integration/customers").status_code == 401
    assert client.get("/integration/customers", headers={"X-Nabhi-Key": "wrong-key-that-is-long-enough-000"}).status_code == 401
    found = client.get("/integration/customers?q=mercury", headers={"X-Nabhi-Key": KEY}).json()["items"]
    assert [(c["name"], c["address"], c["email"]) for c in found] == [("Mercury Drug Makati", "Ayala Ave, Makati", "buy@mercury.test")]
    one = client.get(f"/integration/customers/{made['id']}", headers={"X-Nabhi-Key": KEY}).json()
    assert one["id"] == made["id"] and one["tin"] is None
    assert client.get("/integration/customers/nope", headers={"X-Nabhi-Key": KEY}).status_code == 404
