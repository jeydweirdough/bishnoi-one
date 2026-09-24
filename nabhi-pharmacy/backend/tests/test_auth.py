"""Signing in and out of the Pharmacy, with its own accounts."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import SignInSession, User
from app.security import hash_password

from .conftest import PASSWORD, bearer, sign_in


def test_health(client):
    assert client.get("/health").json() == {"ok": True, "app": "pharmacy"}


def test_sign_in_and_see_who_you_are(client):
    r = sign_in(client, "ANA@example.com")
    assert r.status_code == 200, r.text
    assert r.json()["expiresIn"] == 10 * 3600
    me = client.get("/auth/me", headers=bearer(r)).json()
    assert me["user"]["email"] == "ana@example.com" and me["user"]["fullName"] == "Ana Reyes"
    assert me["role"]["name"] == "Administrator"
    assert [m["key"] for m in me["modules"]] == ["pharmacy"]
    assert me["canManageSettings"] is True
    assert "prescriptions.verify" in me["permissions"]


def test_what_each_role_may_do(client, ben, cy):
    pharmacist = client.get("/auth/me", headers=ben).json()
    assistant = client.get("/auth/me", headers=cy).json()
    assert "prescriptions.verify" in pharmacist["permissions"] and "dispensing.create" in pharmacist["permissions"]
    assert pharmacist["canManageSettings"] is False
    # Takes prescriptions in, but doesn't pass them or hand them over.
    assert "prescriptions.create" in assistant["permissions"]
    assert "prescriptions.verify" not in assistant["permissions"] and "dispensing.create" not in assistant["permissions"]


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


def test_switching_someone_off_ends_their_sessions(client, app):
    headers = bearer(sign_in(client, "ben@example.com"))
    with app.state.sessions() as db:
        db.query(User).filter_by(email="ben@example.com").one().is_active = False
        db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert sign_in(client, "ben@example.com").status_code == 401


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


def test_demo_accounts_list_only_what_exists_here(client, app):
    from app.demo import DEMO_ACCOUNTS, DEMO_PASSWORD

    from .conftest import role_id

    assert client.get("/auth/demo-accounts").json()["items"] == []
    first = DEMO_ACCOUNTS[0]
    with app.state.sessions() as db:
        db.add(User(email=first.email, full_name=first.name, password_hash=hash_password(DEMO_PASSWORD), role_id=role_id(db, first.access)))
        db.commit()
    listed = client.get("/auth/demo-accounts").json()
    assert [d["email"] for d in listed["items"]] == [first.email]
    assert sign_in(client, first.email, listed["password"]).status_code == 200


def test_no_demo_accounts_in_production(tmp_path):
    settings = Settings(_env_file=None, environment="production", allowed_hosts=["testserver"], database_url=f"sqlite:///{(tmp_path / 'p.db').as_posix()}")
    with TestClient(create_app(settings)) as c:
        assert c.get("/auth/demo-accounts").status_code == 404


def test_the_first_admin_comes_from_the_settings_once(tmp_path):
    url = f"sqlite:///{(tmp_path / 'first.db').as_posix()}"
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=url,
                        first_admin_email="Boss@Example.com", first_admin_password=PASSWORD)
    with TestClient(create_app(settings)) as c:
        me = c.get("/auth/me", headers=bearer(sign_in(c, "boss@example.com"))).json()
        assert me["role"]["name"] == "Administrator"
