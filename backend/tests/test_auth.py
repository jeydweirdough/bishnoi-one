"""Signing in and out of this app, with its own accounts."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import SignInSession, User
from app.routers.auth import attempts
from app.security import hash_password

PASSWORD = "correct horse battery"


@pytest.fixture
def app(tmp_path):
    attempts.clear()
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role="admin"))
        db.add(User(email="ben@example.com", full_name="Ben Cruz", password_hash=hash_password(PASSWORD)))
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


def test_health(client):
    assert client.get("/health").json() == {"ok": True, "app": "licensing"}


def test_sign_in_and_see_who_you_are(client):
    r = sign_in(client, "ANA@example.com")
    assert r.status_code == 200, r.text
    assert r.json()["expiresIn"] == 10 * 3600
    me = client.get("/auth/me", headers=bearer(r)).json()
    assert me["user"]["email"] == "ana@example.com" and me["user"]["fullName"] == "Ana Reyes"
    assert me["isDeveloperAdmin"] is False
    assert [m["key"] for m in me["modules"]] == ["inlicensing"]


def test_admins_run_settings_members_dont(client):
    ana = client.get("/auth/me", headers=bearer(sign_in(client))).json()
    ben = client.get("/auth/me", headers=bearer(sign_in(client, "ben@example.com"))).json()
    assert ana["canManageSettings"] is (not False)
    assert ben["canManageSettings"] is False


def test_wrong_password_and_unknown_email_look_the_same(client):
    wrong = sign_in(client, password="nope")
    nobody = sign_in(client, "who@example.com")
    assert wrong.status_code == nobody.status_code == 401
    assert wrong.json() == nobody.json()


def test_no_token_or_a_made_up_one(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer made-up"}).status_code == 401


def test_signing_out_ends_the_session(client):
    headers = bearer(sign_in(client))
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_an_expired_session_ends(client, app):
    headers = bearer(sign_in(client))
    with app.state.sessions() as db:
        for s in db.query(SignInSession):
            s.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_switching_someone_off_or_changing_their_password_ends_their_sessions(client, app):
    headers = bearer(sign_in(client, "ben@example.com"))
    with app.state.sessions() as db:
        db.query(User).filter_by(email="ben@example.com").one().password_changed_at = datetime.now(UTC) + timedelta(seconds=1)
        db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401

    headers = bearer(sign_in(client))
    with app.state.sessions() as db:
        db.query(User).filter_by(email="ana@example.com").one().is_active = False
        db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert sign_in(client).status_code == 401


def test_too_many_wrong_passwords_waits(client):
    for _ in range(5):
        assert sign_in(client, password="nope").status_code == 401
    blocked = sign_in(client)  # even the right one, for now
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 60
    assert sign_in(client, "ben@example.com").status_code == 200  # per email


def test_tokens_are_not_stored(client, app):
    token = sign_in(client).json()["accessToken"]
    with app.state.sessions() as db:
        stored = [s.token_hash for s in db.query(SignInSession)]
    assert token not in stored and len(stored) == 1
