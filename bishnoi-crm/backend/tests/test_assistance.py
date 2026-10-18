"""Government assistance applications (PAP) a field agent files for a doctor's patient."""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import Product
from tests.test_field import doctor, field  # noqa: F401 (field is a fixture)

TODAY = datetime.now(ZoneInfo("Asia/Manila")).date().isoformat()


def product_id(app) -> str:
    with app.state.sessions() as db:
        db.add(Product(code="PZG-1", name="PazoGet"))
        db.commit()
        return db.scalar(select(Product.id).where(Product.code == "PZG-1"))


def test_filed_followed_up_and_approved_with_its_receipt(app, client, field):
    pid = product_id(app)
    cruz = doctor(client, field, "Dr. Cruz", "fay")
    sols = doctor(client, field, "Dr. Lim", "sol")
    body = {"program": "dswd", "patientName": "Juan  Dela Cruz", "companyId": cruz["id"], "productIds": [pid], "submittedOn": TODAY}
    a = client.post("/assistance", json=body, headers=field["fay"]).json()
    assert (a["status"], a["patientName"], a["products"][0]["name"], a["doctor"]["name"]) == ("pending", "Juan Dela Cruz", "PazoGet", "Dr. Cruz")
    # Someone else's doctor, a program that isn't one, a day to come: refused.
    assert client.post("/assistance", json={**body, "companyId": sols["id"]}, headers=field["fay"]).status_code == 422
    assert client.post("/assistance", json={**body, "program": "philhealth"}, headers=field["fay"]).status_code == 422
    assert client.post("/assistance", json={**body, "submittedOn": "2999-01-01"}, headers=field["fay"]).status_code == 422
    assert client.post("/assistance", json={**body, "productIds": []}, headers=field["fay"]).status_code == 422

    listed = client.get("/assistance", headers=field["fay"]).json()
    assert listed["counts"]["pending"] == 1 and listed["counts"]["submitted"] == 1 and listed["products"][0]["name"] == "PazoGet"
    assert [p["key"] for p in listed["programs"]] == ["dswd", "pcso", "ovp", "yakap"]
    # Her lead sees it; another team's agent doesn't.
    assert len(client.get("/assistance", headers=field["lia"]).json()["items"]) == 1
    assert client.get("/assistance", headers=field["sol"]).json()["items"] == []

    # An approval needs its receipt; then it's the month's point.
    assert client.patch(f"/assistance/{a['id']}", json={"status": "approved"}, headers=field["fay"]).status_code == 422
    ok = client.patch(f"/assistance/{a['id']}", json={"status": "approved", "receiptNo": "AICS-2026-0042"}, headers=field["fay"]).json()
    assert (ok["status"], ok["receiptNo"], ok["decidedOn"]) == ("approved", "AICS-2026-0042", TODAY)
    assert client.get("/assistance", headers=field["fay"]).json()["counts"]["approved"] == 1
    # A decided one stays: it can't be taken back.
    assert client.delete(f"/assistance/{a['id']}", headers=field["fay"]).status_code == 409


def test_one_application_for_several_products(app, client, field):
    pid = product_id(app)
    with app.state.sessions() as db:
        db.add(Product(code="BLT-1", name="Beltro"))
        db.commit()
        beltro = db.scalar(select(Product.id).where(Product.code == "BLT-1"))
    cruz = doctor(client, field, "Dr. Cruz", "fay")
    a = client.post("/assistance", json={"program": "yakap", "patientName": "Pedro Santos", "companyId": cruz["id"], "productIds": [pid, beltro, pid], "submittedOn": TODAY}, headers=field["fay"]).json()
    assert [p["name"] for p in a["products"]] == ["PazoGet", "Beltro"]


def test_denied_then_sent_again(app, client, field):
    pid = product_id(app)
    cruz = doctor(client, field, "Dr. Cruz", "fay")
    a = client.post("/assistance", json={"program": "pcso", "patientName": "Ana Reyes", "companyId": cruz["id"], "productIds": [pid], "submittedOn": TODAY}, headers=field["fay"]).json()
    denied = client.patch(f"/assistance/{a['id']}", json={"status": "denied", "notes": "Missing indigency certificate"}, headers=field["fay"]).json()
    assert denied["status"] == "denied" and denied["notes"] == "Missing indigency certificate"
    again = client.patch(f"/assistance/{a['id']}", json={"status": "pending", "submittedOn": TODAY}, headers=field["fay"]).json()
    assert (again["status"], again["decidedOn"]) == ("pending", None)
    assert client.delete(f"/assistance/{a['id']}", headers=field["fay"]).status_code == 204


PDF = b"%PDF-1.4 a scan"
PNG = b"\x89PNG\r\n\x1a\n an id"


def test_ids_and_documents_attached(app, client, field):
    pid = product_id(app)
    cruz = doctor(client, field, "Dr. Cruz", "fay")
    a = client.post("/assistance", json={"program": "dswd", "patientName": "Juan Cruz", "companyId": cruz["id"], "productIds": [pid], "submittedOn": TODAY}, headers=field["fay"]).json()
    ids = client.post(f"/assistance/{a['id']}/files", data={"kind": "id"}, files=[("files", ("front.png", PNG, "image/png")), ("files", ("back.png", PNG, "image/png"))], headers=field["fay"])
    assert ids.status_code == 200, ids.text
    docs = client.post(f"/assistance/{a['id']}/files", data={"kind": "document"}, files=[("files", ("form.pdf", PDF, "application/pdf"))], headers=field["fay"]).json()
    assert [(f["kind"], f["name"]) for f in docs["attachments"]] == [("id", "front.png"), ("id", "back.png"), ("document", "form.pdf")]
    # Only a PDF or a photo; read back as it was; another team's agent can't.
    assert client.post(f"/assistance/{a['id']}/files", data={"kind": "id"}, files=[("files", ("x.txt", b"hello", "text/plain"))], headers=field["fay"]).status_code == 422
    assert client.get(f"/assistance/{a['id']}/files/2", headers=field["fay"]).content == PDF
    assert client.get(f"/assistance/{a['id']}/files/2", headers=field["sol"]).status_code == 404
    left = client.delete(f"/assistance/{a['id']}/files/0", headers=field["fay"]).json()
    assert [f["name"] for f in left["attachments"]] == ["back.png", "form.pdf"]
