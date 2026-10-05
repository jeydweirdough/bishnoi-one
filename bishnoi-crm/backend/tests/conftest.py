"""A CRM API on a fresh database for each test, with two people:
Ana, an Administrator, and Ben, a Salesperson."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.db import make_engine
from app.main import create_app
from app.models import Role, User
from app.routers.auth import attempts
from app.security import hash_password
from app.tenants import database_url

PASSWORD = "correct horse battery"
# Encrypts what Settings → Connections saves (app/connections.py); a fixed one, for tests only.
CONNECTIONS_KEY = "hw1jiw2127mesCxmtE37rmZr_cTkKKVt6ENfbbFmiLQ="


def role_id(db, name: str) -> str:
    return db.scalar(select(Role.id).where(Role.name == name))


# TEST_DATABASE_URL runs every test on that Postgres database instead, emptied
# before each one (so never point it at a database that matters).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def fresh_database(tmp_path) -> str:
    """DATABASE_URL for a test. Each company's database is beside it
    (app/tenants.py): on Postgres, those already made are emptied."""
    if not TEST_DATABASE_URL:
        return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    for slug in ("getmeds", "northwind"):
        try:
            engine = make_engine(database_url(TEST_DATABASE_URL, slug))
            with engine.begin() as connection:
                connection.execute(text("DROP SCHEMA public CASCADE"))
                connection.execute(text("CREATE SCHEMA public"))
        except OperationalError:
            pass  # not made yet: it will be, empty
        finally:
            engine.dispose()
    return TEST_DATABASE_URL


@pytest.fixture
def app(tmp_path):
    attempts.clear()
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path), files_dir=tmp_path / "files", connections_key=CONNECTIONS_KEY)
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Administrator")))
        db.add(User(email="ben@example.com", full_name="Ben Cruz", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Salesperson")))
        db.commit()
    yield app
    # Let go of every company's connections, so the next test can empty them.
    app.state.tenants.close()


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
