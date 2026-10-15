"""Promotional material designs Admin sends for the pharmacist's approval
(routers/material_reviews.py): they land in the inbox, the pharmacist approves,
returns with comments or rejects, and Admin reads the answer back."""

import base64

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import User
from app.routers.auth import attempts
from app.security import hash_password
from tests.conftest import PASSWORD, bearer, fresh_database, role_id, sign_in

KEY = "a" * 32
ADMIN = {"X-Bishnoi-Key": KEY}
PDF = b"%PDF-1.4 leaflet"


@pytest.fixture
def app(tmp_path):
    attempts.clear()
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path), integration_keys=[f"exec:{KEY}"])
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ben@example.com", full_name="Ben Cruz", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Pharmacist"), license_no="PRC-0048213"))
        db.add(User(email="cy@example.com", full_name="Cy Tan", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Pharmacy Assistant")))
        db.commit()
    yield app
    app.state.sessions.kw["bind"].dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def design(source_id="v-1", version=1, data=PDF, **changes) -> dict:
    body = {
        "sourceId": source_id,
        "reference": "PM-40000001",
        "version": version,
        "title": "Glucare leaflet",
        "kind": "Leaflet",
        "product": "Glucare 500 mg",
        "file": {"name": "leaflet.pdf", "contentType": "application/pdf", "data": base64.b64encode(data).decode()},
        "sentBy": "Mia Marketing",
    }
    body.update(changes)
    return body


def test_only_an_app_with_a_key_can_send(client):
    assert client.post("/integration/materials", json=design()).status_code == 401
    assert client.post("/integration/materials", json=design(), headers={"X-Bishnoi-Key": "wrong"}).status_code == 401
    assert client.post("/integration/materials", json=design(data=b"plain text"), headers=ADMIN).status_code == 422


def test_returned_then_approved_and_admin_reads_each_answer(client):
    ben = bearer(sign_in(client, "ben@example.com"))
    cy = bearer(sign_in(client, "cy@example.com"))

    r = client.post("/integration/materials", json=design(), headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "waiting" and r.json()["number"].startswith("PMR-")
    # Sent again while waiting: the same review, updated.
    again = client.post("/integration/materials", json=design(notes="Logo fixed."), headers=ADMIN).json()
    assert again["number"] == r.json()["number"]

    inbox = client.get("/material-reviews", headers=cy).json()
    assert inbox["counts"]["waiting"] == 1
    first = inbox["items"][0]
    assert (first["title"], first["notes"]) == ("Glucare leaflet", "Logo fixed.")
    assert client.get(f"/material-reviews/{first['id']}/file", headers=cy).content == PDF
    assert client.get(f"/material-reviews/{first['id']}", headers=cy).json()["canDecide"] is False  # the assistant only sees
    assert client.post(f"/material-reviews/{first['id']}/decision", json={"outcome": "approved"}, headers=cy).status_code == 403

    # Returned needs a comment.
    assert client.post(f"/material-reviews/{first['id']}/decision", json={"outcome": "returned"}, headers=ben).status_code == 422
    r = client.post(f"/material-reviews/{first['id']}/decision", json={"outcome": "returned", "comments": "Add the FDA registration number."}, headers=ben)
    assert r.status_code == 200, r.text
    answer = client.get("/integration/materials/v-1", headers=ADMIN).json()
    assert (answer["outcome"], answer["comments"], answer["reviewedBy"]) == ("returned", "Add the FDA registration number.", "Ben Cruz")
    # Decided: sending it again changes nothing, and it can't be decided twice.
    assert client.post("/integration/materials", json=design(), headers=ADMIN).json()["outcome"] == "returned"
    assert client.post(f"/material-reviews/{first['id']}/decision", json={"outcome": "approved"}, headers=ben).status_code == 409

    # Version 2 shows version 1 and its comments beside it; approved.
    client.post("/integration/materials", json=design("v-2", 2, notes="FDA registration number added."), headers=ADMIN)
    second = client.get("/material-reviews?status=waiting", headers=ben).json()["items"][0]
    one = client.get(f"/material-reviews/{second['id']}", headers=ben).json()
    assert [(e["version"], e["comments"]) for e in one["earlier"]] == [(1, "Add the FDA registration number.")]
    client.post(f"/material-reviews/{second['id']}/decision", json={"outcome": "approved"}, headers=ben)
    assert client.get("/integration/materials/v-2", headers=ADMIN).json()["outcome"] == "approved"
    assert client.get("/integration/materials/nope", headers=ADMIN).status_code == 404
