"""Stage M3, second part (2026-11-18): one sign-in for the whole system. A module of the one backend
takes the Bishnoi One account's own session token, asking the Platform in-process who it is
(GET /internal/session, modules/one_session.py); nothing outside can ask that.

Real apps on fresh SQLite databases, registered the way backend/main.py registers them."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from modules import inprocess, one_session
from modules.dispatch import Modules
from modules.platform import addresses
from modules.platform.config import Settings as PlatformSettings
from modules.platform.main import create_app as platform_app
from modules.platform.models import Account, User
from modules.platform.security import hash_password
from modules.platform.tests.conftest import PASSWORD, app_id, bearer, make_company, sign_in

BASE = "http://127.0.0.1:8300"
HOSTS = ["testserver", "127.0.0.1"]
# Module package -> (its key on the Platform, its path in the one backend).
MODULES = {"crm": ("crm", "/crm"), "inventory": ("inventory", "/inventory"), "finance": ("finance", "/finance"),
           "pharmacy": ("pharmacy", "/pharmacy")}


@pytest.fixture
def platform(tmp_path):
    one_session.forget_all()
    (tmp_path / "platform").mkdir()
    settings = PlatformSettings(_env_file=None, allowed_hosts=HOSTS, backend_url=BASE,
                                database_url=f"sqlite:///{(tmp_path / 'platform' / 'test.db').as_posix()}")
    app = platform_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role="admin"))
        db.commit()
    inprocess.register(BASE, "platform", "/platform", app)
    yield app
    inprocess.clear()
    addresses.configure(None)
    one_session.forget_all()
    app.state.sessions.kw["bind"].dispose()


def person(platform, given=("crm", "inventory", "finance", "pharmacy"), company_apps=("crm", "inventory", "finance", "pharmacy")) -> dict:
    """Jade at GetMeds, given `given` as Administrator there, signed in to Bishnoi One: her account token."""
    with TestClient(platform) as c:
        ana = bearer(sign_in(c))
        company = make_company(c, ana, apps=company_apps)
        made = c.post("/platform/users", json={"companyId": company["id"], "fullName": "Jade Madigal", "email": "jade@getmeds.test"}, headers=ana).json()["user"]
        for key in given:
            r = c.put(f"/platform/users/{made['id']}/applications/{app_id(c, ana, key)}", json={"role": "Administrator"}, headers=ana)
            assert r.status_code == 200, r.text
        password = c.post(f"/platform/users/{made['id']}/password", json={}, headers=ana).json()["password"]
        r = c.post("/identity/login", json={"email": "jade@getmeds.test", "password": password})
        assert r.status_code == 200, r.text
    return {"token": r.json()["accessToken"], "company": company}


def build(name: str, tmp_path):
    """The module's real app, connected to the Platform at BACKEND_URL + /platform, registered in-process."""
    import importlib

    config = importlib.import_module(f"modules.{name}.config")
    main = importlib.import_module(f"modules.{name}.main")
    for cache in ("company", "platform_links"):
        try:
            forget = importlib.import_module(f"modules.{name}.{cache}").forget
        except (ImportError, AttributeError):
            continue
        forget()
    (tmp_path / name).mkdir()
    settings = config.Settings(_env_file=None, allowed_hosts=HOSTS, platform_api_url=f"{BASE}/platform",
                               database_url=f"sqlite:///{(tmp_path / name / 'test.db').as_posix()}")
    app = main.create_app(settings)
    key, path = MODULES[name]
    inprocess.register(BASE, key, path, app)
    return app


def close(app) -> None:
    tenants = getattr(app.state, "tenants", None)
    if tenants is not None:
        tenants.close()
    else:
        app.state.sessions.kw["bind"].dispose()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("name", ["crm", "inventory", "finance", "pharmacy"])
def test_a_module_takes_the_account_token(platform, tmp_path, name):
    jade = person(platform)
    app = build(name, tmp_path)
    try:
        with TestClient(app) as c:
            r = c.get("/auth/me", headers=auth(jade["token"]))
            assert r.status_code == 200, r.text
            assert "jade@getmeds.test" in r.text
            # Kept for a minute: the next request doesn't ask the Platform again.
            assert any(k[0] == MODULES[name][0] for k in one_session._kept)
            again = c.get("/auth/me", headers=auth(jade["token"]))
            assert again.status_code == 200 and again.json() == r.json()
        # Added once, from the Platform, as a pass would have added her.
        sessions = app.state.tenants.get(jade["company"]["slug"]).sessions if hasattr(app.state, "tenants") else app.state.sessions
        users = __import__(f"modules.{name}.models", fromlist=["User"]).User
        with sessions() as db:
            found = db.scalars(select(users).where(users.email == "jade@getmeds.test")).all()
            assert len(found) == 1 and found[0].platform_identity_id
    finally:
        close(app)


def test_a_module_not_given_to_the_person_refuses(platform, tmp_path):
    jade = person(platform, given=("crm",))
    app = build("pharmacy", tmp_path)
    try:
        with TestClient(app) as c:
            r = c.get("/auth/me", headers=auth(jade["token"]))
        assert r.status_code == 403 and "doesn't include Pharmacy" in r.json()["detail"]
        assert not any(k[0] == "pharmacy" for k in one_session._kept)  # a refusal is never kept
    finally:
        close(app)


def test_signing_out_ends_it_in_every_module_at_once(platform, tmp_path):
    jade = person(platform)
    app = build("finance", tmp_path)
    try:
        with TestClient(app) as c:
            assert c.get("/auth/me", headers=auth(jade["token"])).status_code == 200
            with TestClient(platform) as p:
                assert p.post("/identity/logout", headers=auth(jade["token"])).status_code == 204
            assert not one_session._kept  # dropped by the sign-out, not left to run out
            r = c.get("/auth/me", headers=auth(jade["token"]))
            assert r.status_code == 401
    finally:
        close(app)


def test_a_handed_over_password_must_be_changed_first(platform, tmp_path):
    jade = person(platform)
    with platform.state.sessions() as db:
        account = db.scalar(select(Account).where(Account.email == "jade@getmeds.test"))
        account.must_change_password = True
        db.commit()
    app = build("crm", tmp_path)
    try:
        with TestClient(app) as c:
            r = c.get("/auth/me", headers=auth(jade["token"]))
        assert r.status_code == 403 and "Change the password" in r.json()["detail"]
    finally:
        close(app)


def test_the_crm_takes_the_company_from_the_platform_not_the_token(platform, tmp_path):
    jade = person(platform)
    app = build("crm", tmp_path)
    try:
        with TestClient(app) as c:
            # No company prefix, no company header: the Platform's answer says GetMeds.
            assert c.get("/auth/me", headers=auth(jade["token"])).status_code == 200
        # A made-up token with no prefix is refused as a sign-in that ended, never taken for a company.
        with TestClient(app) as c:
            assert c.get("/auth/me", headers=auth("x" * 43)).status_code == 401
    finally:
        close(app)


def test_nothing_outside_can_ask_who_a_session_is(platform):
    jade = person(platform)
    with TestClient(platform) as c:
        assert c.get("/internal/session", params={"app": "crm"}, headers=auth(jade["token"])).status_code == 404
    # Through the backend's front door, a planted mark is taken out.
    front = Modules(FastAPI(), [("/platform", platform)])

    async def planted(scope, receive, send):
        await front({**scope, inprocess.MARK: "crm"}, receive, send)

    with TestClient(planted, base_url=BASE) as c:
        assert c.get("/platform/internal/session", params={"app": "crm"}, headers=auth(jade["token"])).status_code == 404
    # In-process, a module asks about itself only.
    assert inprocess.get("crm", f"{BASE}/platform/internal/session", params={"app": "finance"}, headers=auth(jade["token"])).status_code == 404
    r = inprocess.get("crm", f"{BASE}/platform/internal/session", params={"app": "crm"}, headers=auth(jade["token"]))
    assert r.status_code == 200 and r.json()["email"] == "jade@getmeds.test" and r.json()["companySlug"] == jade["company"]["slug"]


def test_outside_the_one_backend_a_module_takes_only_its_own_sessions(platform, tmp_path):
    jade = person(platform)
    app = build("pharmacy", tmp_path)
    try:
        inprocess.clear()  # a module run alone: the account token is nothing to it
        with TestClient(app) as c:
            assert c.get("/auth/me", headers=auth(jade["token"])).status_code == 401
    finally:
        close(app)


def test_view_as_works_with_the_account_token(platform, tmp_path):
    from modules.finance.models import Role as FinanceRole, User as FinanceUser
    from modules.finance.platform_roles import VIEW_AS_HEADER
    from modules.finance.security import hash_password as finance_hash

    jade = person(platform)
    app = build("finance", tmp_path)
    try:
        with app.state.sessions() as db:
            role = db.scalars(select(FinanceRole).where(~FinanceRole.is_system)).first() or db.scalars(select(FinanceRole)).first()
            ben = FinanceUser(email="ben@getmeds.test", full_name="Ben Cruz", password_hash=finance_hash(PASSWORD), role_id=role.id)
            db.add(ben)
            db.commit()
            ben_id = ben.id
        with TestClient(app) as c:
            r = c.get("/auth/me", headers={**auth(jade["token"]), VIEW_AS_HEADER: ben_id})
            assert r.status_code == 200 and "ben@getmeds.test" in r.text, r.text
            # Read-only while viewing as someone.
            assert c.post("/auth/view-as", json={"userId": ben_id}, headers={**auth(jade["token"]), VIEW_AS_HEADER: ben_id}).status_code == 403
    finally:
        close(app)
