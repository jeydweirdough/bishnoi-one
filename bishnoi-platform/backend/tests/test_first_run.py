"""Nothing to set up by hand (decided 2026-10-27): the signing key is kept in the
database, the first administrator is made on the setup screen with a code from
the log, and the one app finds each API's address here."""

import logging

from fastapi.testclient import TestClient

from app import passes
from app.config import Settings
from app.main import create_app
from app.models import PlatformSetting
from tests.conftest import PASSWORD, fresh_database


def a_new_platform(tmp_path, **extra) -> TestClient:
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path), **extra)
    return TestClient(create_app(settings))


def test_production_keeps_its_signing_key_in_the_database(tmp_path):
    url = fresh_database(tmp_path)
    first = Settings(_env_file=None, environment="production", allowed_hosts=["testserver"], database_url=url)
    app = create_app(first)
    with app.state.sessions() as db:
        kept = db.get(PlatformSetting, passes.KEPT_AS).value["key"]
    assert first.pass_signing_key.get_secret_value() == kept
    # Started again (another server, a redeploy): the same key, so passes and saved secrets still work.
    again = Settings(_env_file=None, environment="production", allowed_hosts=["testserver"], database_url=url)
    create_app(again)
    assert passes.public_key(again) == passes.public_key(first)
    # Nobody can read it: Settings shows only its own sections.
    assert "signing_key" not in str(TestClient(app).get("/setup").json())


def test_a_set_key_wins(tmp_path):
    key = passes.new_signing_key()
    settings = Settings(_env_file=None, environment="production", allowed_hosts=["testserver"], database_url=fresh_database(tmp_path), pass_signing_key=key)
    app = create_app(settings)
    assert settings.pass_signing_key.get_secret_value() == key
    with app.state.sessions() as db:
        assert db.get(PlatformSetting, passes.KEPT_AS) is None


def test_the_first_administrator_is_made_on_the_setup_screen(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="platform.setup"):
        client = a_new_platform(tmp_path)
    code = next(r.getMessage().rsplit(" ", 1)[1] for r in caplog.records if "setup code" in r.getMessage())
    assert client.get("/setup").json() == {"needed": True}

    body = {"code": "AAAA-BBBB-CCCC", "companyName": "GetMeds Philippines", "name": "Ana Reyes", "email": "Ana@GetMeds.ph", "password": PASSWORD}
    wrong = client.post("/setup", json=body)
    assert wrong.status_code == 422 and "setup code" in wrong.text

    done = client.post("/setup", json={**body, "code": code.lower()})
    assert done.status_code == 201, done.text
    assert done.json() == {"email": "ana@getmeds.ph", "company": "getmeds-philippines"}
    assert client.get("/setup").json() == {"needed": False}
    # Once only.
    assert client.post("/setup", json={**body, "code": code}).status_code == 409

    # They sign in to Bishnoi One with it, run the company, and are a Platform Admin.
    signed = client.post("/identity/login", json={"email": "ana@getmeds.ph", "password": PASSWORD})
    assert signed.status_code == 200, signed.text
    staff = client.post("/auth/login", json={"email": "ana@getmeds.ph", "password": PASSWORD})
    assert staff.status_code == 200, staff.text


def test_the_one_app_finds_each_api_here(client, ana):
    from tests.conftest import app_id

    crm = app_id(client, ana, "crm")
    assert client.patch(f"/platform/applications/{crm}", json={"apiUrl": "https://crm-api.example.com/"}, headers=ana).status_code == 200
    assert client.get("/public/applications").json()["apis"]["crm"] == "https://crm-api.example.com"
