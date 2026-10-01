"""Tests for Executive Admin RBAC, users management, roles & permissions, and audit log."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Role, User
from app.permissions import ROLE_ADMIN_ID, ROLE_EXEC_ASST_ID
from app.security import hash_password

PASSWORD = "testpassword123"


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        _env_file=None,
        allowed_hosts=["testserver"],
        database_url=f"sqlite:///{(tmp_path / 'rbac_test.db').as_posix()}",
    )
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="admin@example.com", full_name="Admin Exec", password_hash=hash_password(PASSWORD), role_id=ROLE_ADMIN_ID))
        db.add(User(email="asst@example.com", full_name="Assistant Exec", password_hash=hash_password(PASSWORD), role_id=ROLE_EXEC_ASST_ID))
        db.commit()
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def sign_in(client, email="admin@example.com", password=PASSWORD):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


def test_list_users_and_roles(client):
    headers = sign_in(client)
    r = client.get("/admin/users", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "roles" in data
    emails = [u["email"] for u in data["items"]]
    assert "admin@example.com" in emails
    assert "asst@example.com" in emails
    role_names = [r["name"] for r in data["roles"]]
    assert "Administrator" in role_names
    assert "Executive Assistant" in role_names


def test_non_admin_cannot_manage_users(client):
    headers = sign_in(client, email="asst@example.com")
    r = client.get("/admin/users", headers=headers)
    assert r.status_code == 403


def test_create_and_update_user(client):
    headers = sign_in(client)
    # 1. Create a user
    create_res = client.post(
        "/admin/users",
        headers=headers,
        json={
            "email": "officer@example.com",
            "fullName": "Compliance Officer Maria",
            "roleId": ROLE_EXEC_ASST_ID,
            "password": "strongPassword123",
        },
    )
    assert create_res.status_code == 201
    user_id = create_res.json()["id"]

    # 2. Update user full name
    patch_res = client.patch(
        f"/admin/users/{user_id}",
        headers=headers,
        json={"fullName": "Maria Santos"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["fullName"] == "Maria Santos"

    # 3. Switch off user
    off_res = client.patch(
        f"/admin/users/{user_id}",
        headers=headers,
        json={"isActive": False},
    )
    assert off_res.status_code == 200
    assert off_res.json()["isActive"] is False

    # 4. Password reset
    pw_res = client.post(
        f"/admin/users/{user_id}/password",
        headers=headers,
        json={"password": "newStrongPassword999"},
    )
    assert pw_res.status_code == 204


def test_admin_cannot_switch_off_themselves(client):
    headers = sign_in(client)
    me = client.get("/auth/me", headers=headers).json()
    my_id = me["user"]["id"]
    r = client.patch(f"/admin/users/{my_id}", headers=headers, json={"isActive": False})
    assert r.status_code == 409


def test_roles_crud_and_protections(client):
    headers = sign_in(client)
    # 1. List roles and permission catalogue
    roles_res = client.get("/admin/roles", headers=headers)
    assert roles_res.status_code == 200
    data = roles_res.json()
    assert len(data["roles"]) >= 4
    catalogue_keys = [c["key"] for c in data["catalogue"]]
    assert "permits" in catalogue_keys
    assert "tickets" in catalogue_keys
    assert "admin" in catalogue_keys

    # 2. Create custom role
    create_role = client.post(
        "/admin/roles",
        headers=headers,
        json={
            "name": "Custom Facility Coordinator",
            "description": "Handles properties and tickets",
            "permissions": ["properties.view", "properties.edit", "tickets.view", "tickets.resolve"],
        },
    )
    assert create_role.status_code == 201
    role_id = create_role.json()["id"]
    assert "properties.view" in create_role.json()["permissions"]

    # 3. Update role
    patch_role = client.patch(
        f"/admin/roles/{role_id}",
        headers=headers,
        json={
            "description": "Updated description",
            "permissions": ["properties.view", "tickets.view"],
        },
    )
    assert patch_role.status_code == 200
    assert patch_role.json()["description"] == "Updated description"
    assert "properties.edit" not in patch_role.json()["permissions"]

    # 4. Delete custom role
    del_role = client.delete(f"/admin/roles/{role_id}", headers=headers)
    assert del_role.status_code == 204

    # 5. System Administrator role cannot be deleted
    del_admin = client.delete(f"/admin/roles/{ROLE_ADMIN_ID}", headers=headers)
    assert del_admin.status_code == 409


def test_audit_log(client):
    headers = sign_in(client)
    # Perform an action to create an audit entry
    client.post(
        "/admin/roles",
        headers=headers,
        json={
            "name": "Audit Test Role",
            "description": "For audit testing",
            "permissions": ["permits.view"],
        },
    )
    # Read audit log
    audit_res = client.get("/admin/audit", headers=headers)
    assert audit_res.status_code == 200
    items = audit_res.json()["items"]
    assert len(items) > 0
    actions = [i["action"] for i in items]
    assert "role.created" in actions
