"""View as (app/platform_roles.py, decided 2026-10-26): an administrator sees the module exactly as
one of its people does, read-only."""

from tests.test_rbac import app, client, sign_in  # noqa: F401 (fixtures)


def check_view_as(client, admin, other, other_email, admin_email):
    """An administrator sees the module as someone else, read-only; nobody else may."""
    listed = client.get("/auth/view-as", headers=admin)
    assert listed.status_code == 200, listed.text
    roles = listed.json()["roles"]
    assert roles == sorted(roles, key=lambda g: -g["size"])  # the role that may do most, first
    people = {p["email"]: p for g in roles for p in g["people"]}
    them, me_id = people[other_email], people[admin_email]["id"]
    assert client.post("/auth/view-as", json={"userId": them["id"]}, headers=admin).status_code == 200
    as_them = {**admin, "X-Bishnoi-View-As": them["id"]}
    assert other_email in str(client.get("/auth/me", headers=as_them).json())  # answered as them
    assert client.post("/admin/users", json={}, headers=as_them).status_code == 403  # read-only
    # Only administrators view as someone.
    assert client.get("/auth/view-as", headers=other).status_code == 403
    assert client.get("/auth/me", headers={**other, "X-Bishnoi-View-As": me_id}).status_code == 403


def test_an_administrator_views_as_someone(client):  # noqa: F811
    check_view_as(client, sign_in(client), sign_in(client, "asst@example.com"), "asst@example.com", "admin@example.com")
