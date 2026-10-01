"""Orders another Nabhi app sends for the pharmacist's check (routers/integration.py):
they land in Prescriptions, are checked as any other, and the app reads the
verdict back. Sending again updates; a verdict stands; they're never
dispensed from the counter."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import User
from app.routers.auth import attempts
from app.security import hash_password
from tests.conftest import PASSWORD, bearer, fresh_database, role_id, sign_in
from tests.test_workflow import ALL_TICKED, medicine

KEY = "k" * 32
CRM = {"X-Nabhi-Key": KEY}
TODAY = date.today()


@pytest.fixture
def app(tmp_path):
    attempts.clear()
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=fresh_database(tmp_path), integration_keys=[f"crm:{KEY}"])
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ben@example.com", full_name="Ben Cruz", password_hash=hash_password(PASSWORD), role_id=role_id(db, "Pharmacist")))
        db.commit()
    yield app
    app.state.sessions.kw["bind"].dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def ben(client) -> dict:
    return bearer(sign_in(client, "ben@example.com"))


def order(**changes) -> dict:
    body = {
        "sourceId": "quote-1",
        "reference": "Q-2026-00042",
        "customer": {"name": "Riverside Medical Center", "phone": "02 8820 7000"},
        "prescription": {"prescriberName": "Dr. Elena Ramos", "prescriberLicense": "PRC-0112233", "prescribedOn": TODAY.isoformat()},
        "lines": [{"code": "AMX500", "name": "Amoxil 500 mg", "quantity": 30, "unit": "box of 100"}],
        "sentBy": "Rico Padilla",
    }
    body.update(changes)
    return body


def test_only_an_app_with_a_key_can_send_or_read(client):
    assert client.post("/integration/checks", json=order()).status_code == 401
    assert client.post("/integration/checks", headers={"X-Nabhi-Key": "wrong" * 8}, json=order()).status_code == 401
    assert client.get("/integration/checks/quote-1", headers=CRM).status_code == 404


def test_an_order_lands_in_the_inbox_matched_by_code(client, ben):
    m = medicine(client, ben)  # code AMX500
    sent = client.post("/integration/checks", headers=CRM, json=order()).json()
    assert sent["outcome"] == "waiting" and sent["number"].startswith("RX-") and sent["reference"] == "Q-2026-00042"
    assert sent["lines"][0]["matchedTo"] == m["label"]
    inbox = client.get("/prescriptions?view=inbox", headers=ben).json()
    assert [(r["number"], r["source"]) for r in inbox] == [(sent["number"], {"app": "crm", "reference": "Q-2026-00042", "sentBy": "Rico Padilla"})]
    assert inbox[0]["patient"]["fullName"] == "Riverside Medical Center"


def test_the_pharmacists_verdict_goes_back(client, ben):
    medicine(client, ben)
    sent = client.post("/integration/checks", headers=CRM, json=order()).json()
    rx = client.get(f"/prescriptions/{sent['id']}", headers=ben).json()
    matches = [{"itemId": i["id"], "medicineId": i["medicine"]["id"]} for i in rx["items"]]
    r = client.post(f"/prescriptions/{rx['id']}/check", headers=ben, json={"checks": ALL_TICKED, "matches": matches, "status": "verified"})
    assert r.status_code == 200, r.text
    back = client.get("/integration/checks/quote-1", headers=CRM).json()
    assert (back["outcome"], back["checkedBy"]) == ("verified", "Ben Cruz")
    assert all(c["done"] for c in back["checks"])


def test_clarification_then_sent_again_goes_back_to_the_inbox(client, ben):
    medicine(client, ben)
    sent = client.post("/integration/checks", headers=CRM, json=order()).json()
    client.post(f"/prescriptions/{sent['id']}/check", headers=ben, json={"checks": {}, "status": "needs_clarification", "notes": "Licence number is unreadable."})
    back = client.get("/integration/checks/quote-1", headers=CRM).json()
    assert (back["outcome"], back["note"]) == ("needs_clarification", "Licence number is unreadable.")
    fixed = order(prescription={"prescriberName": "Dr. Elena Ramos", "prescriberLicense": "PRC-0112234", "prescribedOn": TODAY.isoformat()})
    again = client.post("/integration/checks", headers=CRM, json=fixed).json()
    assert again["id"] == sent["id"] and again["outcome"] == "waiting"  # the same check, not a second one
    assert client.get(f"/prescriptions/{sent['id']}", headers=ben).json()["prescriberLicense"] == "PRC-0112234"


def test_a_verdict_stands_when_sent_again(client, ben):
    sent = client.post("/integration/checks", headers=CRM, json=order()).json()
    client.post(f"/prescriptions/{sent['id']}/check", headers=ben, json={"checks": {}, "status": "rejected", "notes": "Not a valid prescription."})
    again = client.post("/integration/checks", headers=CRM, json=order(lines=[{"name": "Something else", "quantity": 1}])).json()
    assert again["outcome"] == "rejected" and again["lines"][0]["writtenAs"].startswith("Amoxil")


def test_an_old_prescription_is_blocked_and_says_why(client, ben):
    medicine(client, ben)
    old = (TODAY - timedelta(days=400)).isoformat()
    sent = client.post("/integration/checks", headers=CRM, json=order(prescription={"prescriberName": "Dr. Ramos", "prescribedOn": old})).json()
    assert any("days old" in b for b in sent["blocking"])


def test_a_sent_check_is_never_dispensed_here(client, ben):
    m = medicine(client, ben)
    client.post("/stock/receivings", headers=ben, json={"receivedOn": TODAY.isoformat(), "reference": "INV-1",
                "lines": [{"medicineId": m["id"], "lotNo": "L1", "expiresOn": (TODAY + timedelta(days=300)).isoformat(), "quantity": 100, "costCentavos": 700}]})
    sent = client.post("/integration/checks", headers=CRM, json=order()).json()
    rx = client.get(f"/prescriptions/{sent['id']}", headers=ben).json()
    matches = [{"itemId": i["id"], "medicineId": i["medicine"]["id"]} for i in rx["items"]]
    client.post(f"/prescriptions/{rx['id']}/check", headers=ben, json={"checks": ALL_TICKED, "matches": matches, "status": "verified"})
    assert client.get("/dispensing", headers=ben).json() == []
    r = client.get(f"/dispensing/prepare/{rx['id']}", headers=ben)
    assert r.status_code == 409 and "CRM Q-2026-00042" in r.text
