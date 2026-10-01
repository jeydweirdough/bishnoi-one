"""Every record screen asks the role, on the server: seeing, adding, changing
and deleting permits, expatriates, documents, properties and office requests,
and handling renewal alerts, each need their own permission."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import User
from app.permissions import (
    ROLE_ADMIN_ID,
    ROLE_AUDITOR_ID,
    ROLE_COMPLIANCE_ID,
    ROLE_EXEC_ASST_ID,
)
from app.security import hash_password

PASSWORD = "testpassword123"
LATER = (datetime.now(UTC) + timedelta(days=80)).date().isoformat()

PERMIT = {"title": "FDA License to Operate", "category": "fda", "agency": "FDA", "referenceNumber": "LTO-1", "expirationDate": LATER, "renewalWindowDays": 60, "status": "active"}
PROPERTY = {"name": "Tower One", "propertyType": "office", "address": "Ayala Ave", "lessorName": "Ayala Land", "leaseEnd": LATER, "status": "active", "monthlyRent": 1000.0}
TICKET = {"title": "Aircon not cooling", "category": "facilities", "priority": "medium", "status": "open", "requesterName": "Rico", "description": "3rd floor"}


@pytest.fixture
def client(tmp_path):
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{(tmp_path / 'perms.db').as_posix()}")
    app = create_app(settings)
    with app.state.sessions() as db:
        for email, role in (("admin", ROLE_ADMIN_ID), ("asst", ROLE_EXEC_ASST_ID), ("comp", ROLE_COMPLIANCE_ID), ("audit", ROLE_AUDITOR_ID)):
            db.add(User(email=f"{email}@example.com", full_name=email.title(), password_hash=hash_password(PASSWORD), role_id=role))
        db.commit()
    with TestClient(app) as c:
        yield c


def who(client, name) -> dict:
    r = client.post("/auth/login", json={"email": f"{name}@example.com", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


def test_the_auditor_sees_everything_and_changes_nothing(client):
    admin, audit = who(client, "admin"), who(client, "audit")
    permit = client.post("/admin/permits", json=PERMIT, headers=admin).json()
    for path in ("/admin/dashboard", "/admin/permits", "/admin/immigration", "/admin/documents", "/admin/properties", "/admin/tickets", "/admin/notifications"):
        assert client.get(path, headers=audit).status_code == 200, path
    assert client.post("/admin/permits", json=PERMIT, headers=audit).status_code == 403
    assert client.patch(f"/admin/permits/{permit['id']}", json=PERMIT, headers=audit).status_code == 403
    assert client.delete(f"/admin/permits/{permit['id']}", headers=audit).status_code == 403
    assert client.post("/admin/properties", json=PROPERTY, headers=audit).status_code == 403
    assert client.post("/admin/tickets", json=TICKET, headers=audit).status_code == 403
    alert = client.get("/admin/notifications", headers=audit).json()
    if alert:
        assert client.patch(f"/admin/notifications/{alert[0]['id']}/acknowledge", headers=audit).status_code == 403


def test_each_role_does_only_what_it_is_given(client):
    admin, asst, comp = who(client, "admin"), who(client, "asst"), who(client, "comp")
    # The Executive Assistant adds and changes records but deletes none.
    permit = client.post("/admin/permits", json=PERMIT, headers=asst)
    assert permit.status_code == 201, permit.text
    permit = permit.json()
    assert client.patch(f"/admin/permits/{permit['id']}", json={**PERMIT, "title": "FDA LTO"}, headers=asst).status_code == 200
    assert client.delete(f"/admin/permits/{permit['id']}", headers=asst).status_code == 403
    # The Compliance Officer may delete permits, but has nothing to do with properties.
    assert client.post("/admin/properties", json=PROPERTY, headers=comp).status_code == 403
    assert client.delete(f"/admin/permits/{permit['id']}", headers=comp).status_code == 204
    # The Administrator does everything.
    prop = client.post("/admin/properties", json=PROPERTY, headers=admin).json()
    assert client.delete(f"/admin/properties/{prop['id']}", headers=admin).status_code == 204


def test_handing_over_and_closing_a_request_need_their_own_permission(client):
    admin, asst, comp = who(client, "admin"), who(client, "asst"), who(client, "comp")
    ticket = client.post("/admin/tickets", json=TICKET, headers=asst).json()
    # The Compliance Officer may look but not work on office requests.
    assert client.get(f"/admin/tickets/{ticket['id']}", headers=comp).status_code == 200
    assert client.patch(f"/admin/tickets/{ticket['id']}", json={**TICKET, "priority": "high"}, headers=comp).status_code == 403
    # The Assistant edits, assigns and resolves.
    assert client.patch(f"/admin/tickets/{ticket['id']}", json={**TICKET, "assignedTo": "Facilities"}, headers=asst).status_code == 200
    done = client.post(f"/admin/tickets/{ticket['id']}/updates", json={"authorName": "Asst", "content": "Fixed", "updateType": "comment", "newStatus": "resolved"}, headers=asst)
    assert done.status_code == 200, done.text
    assert client.delete(f"/admin/tickets/{ticket['id']}", headers=asst).status_code == 403
    assert client.delete(f"/admin/tickets/{ticket['id']}", headers=admin).status_code == 204


def test_the_red_counts_go_to_who_can_fix_them(client):
    admin, audit = who(client, "admin"), who(client, "audit")
    client.post("/admin/properties", json={**PROPERTY, "monthlyRent": None}, headers=admin)
    assert client.get("/admin/unset", headers=admin).json() == {"propertyRent": 1}
    assert client.get("/admin/unset", headers=audit).json() == {}
