"""Executive Admin endpoints tests: permits, immigration, documents, properties, tickets, and countdown notifications."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.demo import seed_demo_data
from app.main import create_app
from app.models import User
from app.security import hash_password

PASSWORD = "testpassword123"


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        _env_file=None,
        allowed_hosts=["testserver"],
        database_url=f"sqlite:///{(tmp_path / 'exec_test.db').as_posix()}",
        org_timezone="Asia/Manila",
    )
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="admin@example.com", full_name="Admin Exec", password_hash=hash_password(PASSWORD), role="admin"))
        db.commit()
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_header(client):
    r = client.post("/auth/login", json={"email": "admin@example.com", "password": PASSWORD})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


def test_empty_dashboard(client, auth_header):
    r = client.get("/admin/dashboard", headers=auth_header)
    assert r.status_code == 200
    data = r.json()
    assert "stats" in data
    assert "countdownHighlights" in data
    assert data["stats"]["permits"]["total"] == 0


def test_permits_crud_and_countdown(client, auth_header):
    future_date = (datetime.now(UTC) + timedelta(days=25)).date().isoformat()
    # 1. Create permit
    payload = {
        "title": "BOC CPRS Importer Accreditation",
        "category": "boc",
        "agency": "Bureau of Customs (BOC)",
        "referenceNumber": "BOC-2026-9999",
        "expirationDate": future_date,
        "renewalWindowDays": 60,
        "status": "active",
        "responsiblePerson": "Executive Admin",
        "estimatedCost": 15000.0,
        "notes": "Customs clearance required.",
    }
    create_res = client.post("/admin/permits", json=payload, headers=auth_header)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["title"] == "BOC CPRS Importer Accreditation"
    assert created["daysRemaining"] in [24, 25, 26]
    assert created["urgencyTier"] == "approaching"
    permit_id = created["id"]

    # 2. List permits
    list_res = client.get("/admin/permits", headers=auth_header)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Update permit
    payload["status"] = "pending_renewal"
    patch_res = client.patch(f"/admin/permits/{permit_id}", json=payload, headers=auth_header)
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "pending_renewal"

    # 4. Check notification generated
    notifs = client.get("/admin/notifications", headers=auth_header).json()
    assert any(n["entityId"] == permit_id for n in notifs)


def test_immigration_crud(client, auth_header):
    future_date = (datetime.now(UTC) + timedelta(days=12)).date().isoformat()
    payload = {
        "individualName": "Alexander Vance",
        "designation": "Managing Director",
        "nationality": "British",
        "documentType": "acr_card",
        "documentNumber": "ACR-9481928",
        "expirationDate": future_date,
        "renewalLeadDays": 60,
        "status": "expiring_soon",
        "assignedAssistant": "Executive Assistant",
        "notes": "Annual report required.",
    }
    r = client.post("/admin/immigration", json=payload, headers=auth_header)
    assert r.status_code == 201
    immig = r.json()
    assert immig["individualName"] == "Alexander Vance"
    assert immig["urgencyTier"] == "urgent"


def test_documents_crud(client, auth_header):
    future_date = (datetime.now(UTC) + timedelta(days=45)).date().isoformat()
    payload = {
        "title": "Directors & Officers (D&O) Liability Insurance",
        "category": "insurance",
        "counterparty": "Malayan Insurance",
        "referenceNumber": "POL-DO-001",
        "expirationDate": future_date,
        "autoRenews": False,
        "noticePeriodDays": 30,
        "custodian": "Corporate Secretary",
        "status": "active",
        "annualValue": 250000.0,
    }
    r = client.post("/admin/documents", json=payload, headers=auth_header)
    assert r.status_code == 201
    doc = r.json()
    assert doc["title"] == "Directors & Officers (D&O) Liability Insurance"


def test_properties_crud(client, auth_header):
    future_date = (datetime.now(UTC) + timedelta(days=80)).date().isoformat()
    payload = {
        "name": "Tower One Makati Headquarters",
        "propertyType": "office",
        "address": "Ayala Ave, Makati City",
        "lessorName": "Ayala Land Offices",
        "leaseEnd": future_date,
        "noticeDeadlineDays": 90,
        "monthlyRent": 350000.0,
        "status": "active",
        "assignedManager": "Executive Admin",
    }
    r = client.post("/admin/properties", json=payload, headers=auth_header)
    assert r.status_code == 201
    prop = r.json()
    assert prop["name"] == "Tower One Makati Headquarters"


def test_tickets_flow(client, auth_header):
    payload = {
        "title": "Boardroom A HVAC Malfunction",
        "category": "facilities",
        "priority": "urgent",
        "status": "open",
        "requesterName": "Carmen Villanueva",
        "requesterEmail": "carmen@example.com",
        "description": "Air conditioning unit leaking before executive meeting.",
    }
    create_res = client.post("/admin/tickets", json=payload, headers=auth_header)
    assert create_res.status_code == 201
    ticket = create_res.json()
    assert ticket["ticketNumber"].startswith("EX-")
    ticket_id = ticket["id"]

    # Add update
    update_payload = {
        "authorName": "Admin Exec",
        "updateType": "status_change",
        "content": "Technician dispatched to Boardroom A.",
        "newStatus": "in_progress",
    }
    up_res = client.post(f"/admin/tickets/{ticket_id}/updates", json=update_payload, headers=auth_header)
    assert up_res.status_code == 200
    assert up_res.json()["status"] == "in_progress"
    assert len(up_res.json()["updates"]) >= 2


def test_demo_seeding(app, client, auth_header):
    with app.state.sessions() as db:
        seed_demo_data(db, app.state.settings)
    r = client.get("/admin/dashboard", headers=auth_header)
    assert r.status_code == 200
    data = r.json()
    assert data["stats"]["permits"]["total"] > 0
    assert data["stats"]["immigration"]["total"] > 0
    assert data["stats"]["documents"]["total"] > 0
    assert data["stats"]["properties"]["total"] > 0
    assert data["stats"]["tickets"]["totalOpen"] > 0
    assert len(data["countdownHighlights"]) > 0


def test_dashboard_health_and_renewals_by_month(client, auth_header):
    """Each area's records as current, due soon or overdue, and renewals per month."""
    def permit(days, ref):
        due = (datetime.now(UTC) + timedelta(days=days)).date().isoformat()
        body = {"title": f"Permit {ref}", "category": "lgu", "agency": "City Hall", "referenceNumber": ref, "expirationDate": due, "status": "active"}
        assert client.post("/admin/permits", json=body, headers=auth_header).status_code == 201

    permit(-5, "P-1")  # overdue
    permit(10, "P-2")  # within the 30-day window
    permit(200, "P-3")  # current
    data = client.get("/admin/dashboard", headers=auth_header).json()
    permits = next(h for h in data["health"] if h["key"] == "permits")
    assert (permits["total"], permits["current"], permits["dueSoon"], permits["overdue"]) == (3, 1, 1, 1)
    months = data["renewalsByMonth"]
    assert months[0]["month"] == "overdue" and months[0]["permits"] == 1
    assert len(months) == 7 and sum(m["permits"] for m in months[1:]) == 1  # 200 days out is past the six months
