"""Signing in and out of Inventory, with its own accounts."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import SignInSession, User
from app.security import hash_password
from tests.conftest import bearer, settings_for, sign_in


def test_health(client):
    assert client.get("/health").json() == {"ok": True, "app": "inventory"}


def test_sign_in_and_see_who_you_are(client):
    r = sign_in(client, "ANA@example.com")
    assert r.status_code == 200, r.text
    assert r.json()["expiresIn"] == 10 * 3600
    me = client.get("/auth/me", headers=bearer(r)).json()
    assert me["user"]["email"] == "ana@example.com" and me["user"]["fullName"] == "Ana"
    assert me["role"]["name"] == "Administrator"
    assert [m["key"] for m in me["modules"]] == ["inventory"]
    assert "adjustments.approve" in me["permissions"]


def test_the_role_says_what_you_may_do(client):
    ana = client.get("/auth/me", headers=bearer(sign_in(client))).json()
    sal = client.get("/auth/me", headers=bearer(sign_in(client, "sal@example.com"))).json()
    assert ana["canManageSettings"] is True
    assert sal["canManageSettings"] is False
    assert "orders.create" in sal["permissions"] and "receiving.receive" not in sal["permissions"]


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
    headers = bearer(sign_in(client, "sal@example.com"))
    with app.state.sessions() as db:
        db.query(User).filter_by(email="sal@example.com").one().password_changed_at = datetime.now(UTC) + timedelta(seconds=1)
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
    assert sign_in(client, "sal@example.com").status_code == 200  # per email


def test_tokens_are_not_stored(client, app):
    token = sign_in(client).json()["accessToken"]
    with app.state.sessions() as db:
        stored = [s.token_hash for s in db.query(SignInSession)]
    assert token not in stored and len(stored) == 1



def test_demo_accounts_list_only_what_exists_here(client, app):
    from app.demo import DEMO_ACCOUNTS, DEMO_PASSWORD

    assert client.get("/auth/demo-accounts").json()["items"] == []
    first = DEMO_ACCOUNTS[0]
    with app.state.sessions() as db:
        role_id = db.query(User).filter_by(email="wes@example.com").one().role_id
        db.add(User(email=first.email, full_name=first.name, password_hash=hash_password(DEMO_PASSWORD), role_id=role_id))
        db.commit()
    listed = client.get("/auth/demo-accounts").json()
    assert [d["email"] for d in listed["items"]] == [first.email]
    assert sign_in(client, first.email, listed["password"]).status_code == 200


def test_no_demo_accounts_in_production(tmp_path):
    with TestClient(create_app(settings_for(tmp_path, environment="production"))) as c:
        assert c.get("/auth/demo-accounts").status_code == 404


def test_the_first_administrator_comes_from_the_settings(tmp_path):
    """FIRST_ADMIN_*: made into an empty database, and only into an empty one."""
    from pydantic import SecretStr

    first = dict(first_admin_email="Boss@Example.com", first_admin_name="The Boss", first_admin_password=SecretStr("a long first password"))
    settings = settings_for(tmp_path, **first)
    app = create_app(settings)
    with TestClient(app) as c:
        r = c.post("/auth/login", json={"email": "boss@example.com", "password": "a long first password"})
        assert r.status_code == 200
        assert c.get("/auth/me", headers=bearer(r)).json()["role"]["name"] == "Administrator"
    # A second start, with other settings: someone exists, so nothing is made.
    create_app(settings.model_copy(update={"first_admin_email": "x@example.com", "first_admin_password": SecretStr("another long password")}))
    with app.state.sessions() as db:
        assert [u.email for u in db.query(User)] == ["boss@example.com"]
    app.state.sessions.kw["bind"].dispose()
