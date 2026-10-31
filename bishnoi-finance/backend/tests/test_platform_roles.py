"""Roles from Bishnoi One Platform (app/platform_roles.py, decided 2026-10-23):
the Platform sends the company's roles and who holds them, signed; they are kept
in this application's role tables, by name, and people's roles set by email."""

import json
import secrets
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import func, select

from app import platform_roles
from app.models import Role, User
from app.permissions import ALL_PERMISSIONS
from tests.test_platform_sign_in import KEY, app, b64, client, linked, make_pass, take  # noqa: F401 (fixtures)

APP = "finance"
PERMS = sorted(ALL_PERMISSIONS)[:2]
WHO = "ben@example.com"  # someone already here


@pytest.fixture(autouse=True)
def fresh():
    platform_roles._newest.clear()  # what the last test took


def note(kind="roles", key=KEY, **over) -> str:
    """A note as the Platform signs it (bishnoi-platform app/access_roles.py)."""
    now = int(time.time())
    claims = {"iss": "bishnoi-platform", "aud": APP, "kind": kind, "company": "c1", "slug": "getmeds", "iat": now, "exp": now + 600,
              "jti": secrets.token_urlsafe(12), "roles": [], "people": [], **over}
    head = b64(json.dumps({"alg": "EdDSA", "typ": "JWT", "kid": "test"}).encode())
    body = b64(json.dumps(claims).encode())
    return f"{head}.{body}.{b64(key.sign(f'{head}.{body}'.encode()))}"


def database(app):
    tenants = getattr(app.state, "tenants", None)
    return tenants.get("getmeds").sessions if tenants is not None else app.state.sessions


def role_named(app, name):
    with database(app)() as db:
        role = db.scalar(select(Role).where(Role.name == name))
        return (role.id, sorted(g.permission for g in role.grants)) if role else None


def role_of(app, email):
    with database(app)() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        return db.get(Role, user.role_id).name


REP = {"name": "Medical rep", "description": "Made on the Platform", "scope": "team", "permissions": PERMS, "admin": False}


def test_what_a_role_can_hold_here(client):
    r = client.get("/platform/catalog")
    assert r.status_code == 200
    offered = {a["permission"] for area in r.json()["areas"] for a in area["actions"]}
    assert r.json()["app"] == APP and offered and offered <= ALL_PERMISSIONS


def test_the_platforms_roles_are_kept_and_given(app, client, linked):
    r = client.post("/platform/roles", json={"pass": note(roles=[REP], people=[{"email": WHO, "role": "Medical rep", "admin": False}])})
    assert r.status_code == 204, r.text
    role_id, perms = role_named(app, "Medical rep")
    assert perms == PERMS and role_of(app, WHO) == "Medical rep"
    # changed on the Platform: changed here, the same role
    time.sleep(1)
    client.post("/platform/roles", json={"pass": note(roles=[{**REP, "permissions": PERMS[:1]}])})
    assert role_named(app, "Medical rep") == (role_id, PERMS[:1])


def test_the_administrator_stays_this_applications_own(app, client, linked):
    before = role_named(app, "Administrator")
    r = client.post("/platform/roles", json={"pass": note(
        roles=[{"name": "Administrator", "description": None, "scope": None, "permissions": [], "admin": True}],
        people=[{"email": WHO, "role": "Administrator", "admin": True}],
    )})
    assert r.status_code == 204
    assert role_named(app, "Administrator") == before and role_of(app, WHO) == "Administrator"


def test_only_the_platforms_newest_note_is_taken(app, client, linked):
    now = int(time.time())
    for token in (
        note(key=Ed25519PrivateKey.generate(), roles=[REP]),
        note(aud="someone-else", roles=[REP]),
        note(kind="roles-ask", roles=[REP]),
        note(exp=now - 300, roles=[REP]),
    ):
        assert client.post("/platform/roles", json={"pass": token}).status_code == 404
    assert role_named(app, "Medical rep") is None
    assert client.post("/platform/roles", json={"pass": note(iat=now + 5, roles=[REP])}).status_code == 204
    # an older note, sent again: not taken
    assert client.post("/platform/roles", json={"pass": note(iat=now - 60, roles=[{**REP, "permissions": []}])}).status_code == 404
    assert role_named(app, "Medical rep")[1] == PERMS


def test_the_roles_here_today_for_the_platform_to_bring_in(client, linked):
    assert client.post("/platform/roles/export", json={"pass": note()}).status_code == 404  # a "roles" note doesn't ask
    r = client.post("/platform/roles/export", json={"pass": note(kind="roles-ask")})
    assert r.status_code == 200, r.text
    admin = next(x for x in r.json()["roles"] if x["isSystem"])
    assert admin["name"] == "Administrator"


def test_the_sign_in_pass_brings_the_role_with_it(app, client, linked):
    r = take(client, make_pass(role="Night shift", roleDef={"name": "Night shift", "description": None, "scope": "own", "permissions": PERMS, "admin": False}))
    assert r.status_code == 200, r.text
    assert role_of(app, "jade@getmeds.test") == "Night shift" and role_named(app, "Night shift")[1] == PERMS


def test_switched_off_on_the_platform_is_switched_off_here(app, client, linked):
    """R2: the Platform's note says who is switched off; their account here is too, and their sessions end."""
    from app.models import SignInSession

    with database(app)() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == WHO))
        uid = user.id
    r = client.post("/platform/roles", json={"pass": note(people=[{"email": WHO, "role": None, "admin": False, "active": False}])})
    assert r.status_code == 204, r.text
    with database(app)() as db:
        assert db.get(User, uid).is_active is False
        assert db.scalar(select(func.count()).select_from(SignInSession).where(SignInSession.user_id == uid)) == 0
    time.sleep(1)
    client.post("/platform/roles", json={"pass": note(people=[{"email": WHO, "role": None, "admin": False, "active": True}])})
    with database(app)() as db:
        assert db.get(User, uid).is_active is True  # switched on again there: on here


def test_once_connected_people_are_kept_on_the_platform(app, client):
    """R2: connected to the Platform, this application doesn't add people, set passwords, change roles
    or switch people off, and its own password sign-in is closed. What is its own about a person still saves."""
    app.state.settings.platform_api_url = "http://platform.test"
    try:
        assert client.post("/auth/login", json={"email": WHO, "password": "anything-at-all"}).status_code == 403
        assert client.post("/admin/users", json={}).status_code == 409
        assert client.post("/admin/users/x/password", json={"password": "x" * 12}).status_code == 409
        assert client.patch("/admin/users/x", json={"roleId": "r"}).status_code == 409
        assert client.patch("/admin/users/x", json={"isActive": False}).status_code == 409
        assert client.post("/admin/roles", json={}).status_code == 409
        # not the Platform's: answered by the endpoint itself (here, no one is signed in)
        assert client.patch("/admin/users/x", json={"licenseNo": "PRC-1"}).status_code == 409  # kept on the Platform too since 2026-10-30
    finally:
        app.state.settings.platform_api_url = None
