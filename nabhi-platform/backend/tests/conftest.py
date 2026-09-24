"""A Platform API on a fresh database for each test, with two staff:
Ana, a Platform Admin, and Ben, Support.

Nothing is really called: the health probe answers from `probes`, a dict of
address -> Answer that a test can change (anything not in it is operational).
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import monitor
from app.config import Settings
from app.db import make_engine
from app.main import create_app
from app.models import User
from app.routers.auth import attempts
from app.security import hash_password
from app.traffic import traffic

PASSWORD = "correct horse battery"

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


@pytest.fixture
def probes(monkeypatch) -> dict:
    answers: dict[str, monitor.Answer] = {}
    monkeypatch.setattr(monitor, "probe", lambda url, timeout, slow: answers.get(url, monitor.Answer("operational", 12, 200, None)))
    return answers


@pytest.fixture
def app(tmp_path, probes):
    attempts.clear()
    traffic.clear()
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path))
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role="admin"))
        db.add(User(email="ben@example.com", full_name="Ben Cruz", password_hash=hash_password(PASSWORD), role="member"))
        db.commit()
    yield app
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
def ana(client) -> dict:
    return bearer(sign_in(client))


@pytest.fixture
def ben(client) -> dict:
    return bearer(sign_in(client, "ben@example.com"))


def app_id(client, headers, key: str) -> str:
    apps = client.get("/platform/applications", headers=headers).json()["applications"]
    return next(a["id"] for a in apps if a["key"] == key)


def make_company(client, headers, name="GetMeds", apps=("crm", "pharmacy"), **extra) -> dict:
    ids = [app_id(client, headers, k) for k in apps]
    r = client.post("/platform/companies", json={"name": name, "applicationIds": ids, **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["company"]
