"""View as (app/platform_roles.py, decided 2026-10-26): an administrator sees the module exactly as
one of its people does, read-only."""


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
    # A real page's GraphQL read must use the viewed person's identity, not be
    # rejected as a write merely because it travels over POST.
    page = client.post("/graphql", json={"query": "{ me }"}, headers=as_them)
    assert page.status_code == 200, page.text
    assert not page.json().get("errors"), page.text
    assert other_email in str(page.json()["data"]["me"])
    # This endpoint has no mutation schema; allowing its POST never enables writes.
    mutation = client.post("/graphql", json={"query": "mutation { __typename }"}, headers=as_them)
    assert mutation.status_code == 200, mutation.text
    assert mutation.json().get("errors"), mutation.text
    # Leaving preview restores the administrator with the same original token.
    restored = client.post("/graphql", json={"query": "{ me }"}, headers=admin)
    assert restored.status_code == 200, restored.text
    assert admin_email in str(restored.json()["data"]["me"])

    # Only administrators view as someone.
    assert client.get("/auth/view-as", headers=other).status_code == 403
    assert client.get("/auth/me", headers={**other, "X-Bishnoi-View-As": me_id}).status_code == 403


def test_an_administrator_views_as_someone(client, ana, ben):
    check_view_as(client, ana, ben, "ben@example.com", "ana@example.com")
