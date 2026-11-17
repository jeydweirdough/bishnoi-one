"""One backend (2026-11-17): with BACKEND_URL set, every module's address is BACKEND_URL + its
path, whatever address was once registered for it in Applications."""

import pytest
from fastapi.testclient import TestClient

from modules.platform import addresses, links
from modules.platform.config import Settings
from modules.platform.main import create_app
from modules.platform.models import User
from modules.platform.security import hash_password
from modules.platform.tests.conftest import PASSWORD, app_id, bearer, fresh_database, sign_in


@pytest.fixture
def backend_client(tmp_path, probes, monkeypatch):
    monkeypatch.setattr(links, "deliver_later", lambda *a, **k: None)  # nothing is really called
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path), backend_url="http://10.0.1.1:8300/")
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role="admin"))
        db.commit()
    with TestClient(app) as c:
        yield c
    app.state.sessions.kw["bind"].dispose()
    addresses.configure(None)


def test_every_module_is_reported_at_the_one_backend(backend_client):
    client = backend_client
    ana = bearer(sign_in(client))
    # A registered address from the days of one server per app is ignored for a module.
    client.patch(f"/platform/applications/{app_id(client, ana, 'crm')}", json={"apiUrl": "https://crm-api.example.com"}, headers=ana)

    apis = client.get("/public/applications").json()["apis"]
    assert apis["crm"] == "http://10.0.1.1:8300/crm"
    assert apis["inventory"] == "http://10.0.1.1:8300/inventory"
    assert apis["finance"] == "http://10.0.1.1:8300/finance"
    assert apis["exec"] == "http://10.0.1.1:8300/admin"
    assert apis["platform"] == "http://10.0.1.1:8300/platform"

    listed = {a["key"]: a for a in client.get("/platform/applications", headers=ana).json()["applications"]}
    assert listed["crm"]["apiUrl"] == "http://10.0.1.1:8300/crm" and listed["crm"]["inBackend"]
    assert listed["crm"]["healthUrl"] == "http://10.0.1.1:8300/crm/health"

    # Links between modules carry the worked-out address too.
    crm_key = client.post(f"/platform/applications/{app_id(client, ana, 'crm')}/connect-key", headers=ana).json()["key"]
    client.post("/platform/links", json={"fromAppId": app_id(client, ana, "crm"), "toAppId": app_id(client, ana, "inventory")}, headers=ana)
    crm = client.get("/connect/links", headers={"X-Bishnoi-App-Key": crm_key}).json()
    assert crm["uses"]["inventory"]["apiUrl"] == "http://10.0.1.1:8300/inventory"


def test_without_backend_url_the_registered_address_stands(client, ana):
    assert addresses.backend() is None
    assert client.get("/public/applications").json()["apis"]["inventory"] == "http://127.0.0.1:8304"
