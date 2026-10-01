"""A Pharmacy API on a fresh database for each test, with three people:
Ana, an Administrator; Ben, a Pharmacist; Cy, a Pharmacy Assistant."""

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


def role_id(db, name: str) -> str:
    return db.scalar(select(Role.id).where(Role.name == name))


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
def app(tmp_path):
    attempts.clear()
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path))
    app = create_app(settings)
    with app.state.sessions() as db:
        for email, name, role in (
            ("ana@example.com", "Ana Reyes", "Administrator"),
            ("ben@example.com", "Ben Cruz", "Pharmacist"),
            ("cy@example.com", "Cy Tan", "Pharmacy Assistant"),
        ):
            db.add(User(email=email, full_name=name, password_hash=hash_password(PASSWORD), role_id=role_id(db, role)))
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
def ana(client) -> dict:
    return bearer(sign_in(client))


@pytest.fixture
def ben(client) -> dict:
    return bearer(sign_in(client, "ben@example.com"))


@pytest.fixture
def cy(client) -> dict:
    return bearer(sign_in(client, "cy@example.com"))
