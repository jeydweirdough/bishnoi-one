"""A Sales API on a fresh database for each test, with two people:
Ana, an Administrator, and Ben, a Sales Rep."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import Role, User
from app.routers.auth import attempts
from app.security import hash_password

PASSWORD = "correct horse battery"


def role_id(db, name: str) -> str:
    return db.scalar(select(Role.id).where(Role.name == name))


@pytest.fixture
def app(tmp_path):
    attempts.clear()
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", files_dir=tmp_path / "files")
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Administrator")))
        db.add(User(email="ben@example.com", full_name="Ben Cruz", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Sales Rep")))
        db.commit()
    return app


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
