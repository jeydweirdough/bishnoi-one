"""Promotional materials (app/routers/materials.py): designed by the marketing
assistant, approved by the pharmacist in Pharmacy, produced by the executive
office, given out with the CRM manager's approval. Pharmacy and the CRM are
stood in for here (app/linked.py's call)."""

import base64

import pytest
from pydantic import SecretStr

from app import linked
from app.models import User
from app.permissions import ROLE_AUDITOR_ID, ROLE_MARKETING_ID
from app.security import hash_password
from tests.test_rbac import PASSWORD, app, client, sign_in  # noqa: F401 (fixtures)

PDF = b"%PDF-1.4 a design"
JPEG = bytes([0xFF, 0xD8, 0xFF])  # how a JPEG starts


class Apps:
    """Pharmacy and the CRM as Admin sees them."""

    def __init__(self):
        self.reviews: dict[str, dict] = {}  # by version id
        self.requests: dict[str, dict] = {}  # by distribution id
        self.sent: list[tuple[str, str, dict | None]] = []
        self.down = False

    def __call__(self, settings, app, method, path, body=None):
        self.sent.append((app, f"{method} {path}", body))
        if self.down:
            raise linked.Unavailable("Pharmacy can't be reached right now.")
        if app == "pharmacy" and method == "POST":
            self.reviews[body["sourceId"]] = {"number": f"PMR-{len(self.reviews) + 1}", "outcome": "waiting", "body": body}
            return {k: v for k, v in self.reviews[body["sourceId"]].items() if k != "body"}
        if app == "pharmacy":
            return {k: v for k, v in self.reviews[path.rsplit("/", 1)[1]].items() if k != "body"}
        if path == "/integration/teams":
            return {"teams": [{"id": "t-rx", "name": "Rx Makati", "manager": {"id": "u-javed", "name": "Javed Khan"}, "people": [{"id": "u-ana", "name": "Ana Cruz"}]}]}
        if method == "POST":
            self.requests.setdefault(body["sourceId"], {"outcome": "waiting"})["state"] = body["state"]
            return {"outcome": self.requests[body["sourceId"]]["outcome"]}
        return self.requests[path.rsplit("/", 1)[1]]


@pytest.fixture
def apps(app, monkeypatch):
    fake = Apps()
    monkeypatch.setattr(linked, "call", fake)
    app.state.settings = app.state.settings.model_copy(update={
        "pharmacy_api_url": "http://pharmacy.test", "pharmacy_api_key": SecretStr("k1"),
        "crm_api_url": "http://crm.test", "crm_api_key": SecretStr("k2"),
    })
    with app.state.sessions() as db:
        db.add(User(email="mia@example.com", full_name="Mia Marketing", password_hash=hash_password(PASSWORD), role_id=ROLE_MARKETING_ID))
        db.add(User(email="audit@example.com", full_name="Ramon Audit", password_hash=hash_password(PASSWORD), role_id=ROLE_AUDITOR_ID))
        db.commit()
    return fake


def upload(client, material_id, headers, data=PDF, notes=None):
    return client.put(f"/admin/materials/{material_id}/design", files={"file": ("leaflet.pdf", data, "application/pdf")}, data={"notes": notes} if notes else {}, headers=headers)


def expire(app):
    """Makes the other apps' last answers out of date, so the next look asks again."""
    from app.models import PromoDistribution, PromoVersion

    with app.state.sessions() as db:
        for model in (PromoVersion, PromoDistribution):
            for row in db.query(model):
                row.synced_at = None
        db.commit()


def test_from_design_to_given_out(app, client, apps):
    mia = sign_in(client, "mia@example.com")  # the marketing assistant
    asst = sign_in(client, "asst@example.com")  # the executive assistant produces it

    r = client.post("/admin/materials", json={"title": "Glucare leaflet", "kind": "Leaflet", "product": "Glucare 500 mg"}, headers=mia)
    assert r.status_code == 201, r.text
    m = r.json()["material"]
    assert (m["status"], m["version"]) == ("draft", None)
    assert client.post(f"/admin/materials/{m['id']}/submit", headers=mia).status_code == 409  # nothing to send yet

    # Version 1 goes to the pharmacist, who returns it for changes.
    r = upload(client, m["id"], mia)
    assert r.status_code == 200, r.text
    assert r.json()["can"]["submit"] is True
    r = client.post(f"/admin/materials/{m['id']}/submit", headers=mia)
    assert r.status_code == 200, r.text
    sent = apps.sent[-1][2]
    assert (sent["version"], sent["title"], base64.b64decode(sent["file"]["data"])) == (1, "Glucare leaflet", PDF)
    assert r.json()["material"]["status"] == "pharmacy_review"
    v1 = sent["sourceId"]
    apps.reviews[v1].update(outcome="returned", comments="Add the FDA registration number.", reviewedBy="Ph. Liza Reyes", reviewedAt="2026-10-15T05:00:00Z")
    expire(app)
    r = client.get(f"/admin/materials/{m['id']}", headers=mia).json()
    assert r["material"]["status"] == "returned"
    assert r["versions"][0]["comments"] == "Add the FDA registration number."

    # Version 2, corrected, is approved; version 1 keeps its comments.
    upload(client, m["id"], mia, notes="FDA registration number added.")
    client.post(f"/admin/materials/{m['id']}/submit", headers=mia)
    v2 = apps.sent[-1][2]["sourceId"]
    assert v2 != v1
    apps.reviews[v2].update(outcome="approved", reviewedBy="Ph. Liza Reyes")
    expire(app)
    r = client.get(f"/admin/materials/{m['id']}", headers=mia).json()
    assert r["material"]["status"] == "approved"
    assert [(v["number"], v["review"]) for v in r["versions"]] == [(2, "approved"), (1, "returned")]
    assert r["can"]["upload"] is False and r["can"]["produce"] is False  # the marketing assistant doesn't produce

    # The executive assistant produces 500; received, they're in stock.
    assert client.post(f"/admin/materials/{m['id']}/productions", json={"quantity": 500}, headers=mia).status_code == 403
    r = client.post(f"/admin/materials/{m['id']}/productions", json={"quantity": 500, "supplier": "Makati Printers", "cost": 7500}, headers=asst)
    assert r.status_code == 201, r.text
    assert r.json()["material"]["status"] == "in_production"
    run = r.json()["productions"][0]
    assert run["versionNumber"] == 2
    r = client.post(f"/admin/materials/{m['id']}/productions/{run['id']}/received", data={}, headers=asst).json()
    assert (r["material"]["status"], r["material"]["stock"]) == ("available", 500)

    # 200 asked for Ana in Rx Makati; the manager approves; given out.
    teams = client.get("/admin/materials/teams", headers=mia).json()["teams"]
    assert teams[0]["manager"]["name"] == "Javed Khan"
    r = client.post(f"/admin/materials/{m['id']}/distributions", json={"teamId": "t-rx", "recipientId": "u-ana", "quantity": 600}, headers=mia)
    assert r.status_code == 422  # more than there is
    r = client.post(f"/admin/materials/{m['id']}/distributions", json={"teamId": "t-rx", "recipientId": "u-ana", "quantity": 200, "purpose": "Doctor visits in October"}, headers=mia)
    assert r.status_code == 201, r.text
    d = r.json()["distributions"][0]
    assert (d["status"], d["recipientName"], r.json()["material"]["available"]) == ("for_approval", "Ana Cruz", 300)
    assert apps.sent[-1][2]["state"] == "requested"
    assert client.post(f"/admin/materials/{m['id']}/distributions/{d['id']}/distributed", data={}, headers=mia).status_code == 409  # not approved yet

    apps.requests[d["id"]].update(outcome="approved", decidedBy="Javed Khan", note="OK for October.")
    expire(app)
    r = client.get(f"/admin/materials/{m['id']}", headers=mia).json()
    assert (r["distributions"][0]["status"], r["distributions"][0]["managerName"]) == ("approved", "Javed Khan")
    r = client.post(f"/admin/materials/{m['id']}/distributions/{d['id']}/distributed", data={}, headers=mia).json()
    assert (r["material"]["stock"], r["material"]["available"], r["distributions"][0]["status"]) == (300, 300, "distributed")
    assert apps.sent[-1][2]["state"] == "distributed"

    texts = [h["text"] for h in r["history"]]
    assert any("returned for changes" in t for t in texts) and any("approved by Javed Khan" in t for t in texts)


def test_a_rejected_request_frees_its_quantity_and_cancelling_tells_the_crm(app, client, apps):
    mia = sign_in(client, "mia@example.com")
    asst = sign_in(client, "asst@example.com")
    m = client.post("/admin/materials", json={"title": "Desk calendar 2027", "kind": "Calendar"}, headers=mia).json()["material"]
    upload(client, m["id"], mia)
    client.post(f"/admin/materials/{m['id']}/submit", headers=mia)
    apps.reviews[apps.sent[-1][2]["sourceId"]]["outcome"] = "approved"
    expire(app)
    client.get(f"/admin/materials/{m['id']}", headers=mia)
    run = client.post(f"/admin/materials/{m['id']}/productions", json={"quantity": 100}, headers=asst).json()["productions"][0]
    client.post(f"/admin/materials/{m['id']}/productions/{run['id']}/received", data={}, headers=asst)

    first = client.post(f"/admin/materials/{m['id']}/distributions", json={"teamId": "t-rx", "quantity": 60}, headers=mia).json()["distributions"][0]
    assert first["recipientName"] is None and first["teamName"] == "Rx Makati"  # the whole team
    apps.requests[first["id"]].update(outcome="rejected", decidedBy="Javed Khan", note="Too many for this month.")
    expire(app)
    r = client.get(f"/admin/materials/{m['id']}", headers=mia).json()
    assert (r["distributions"][0]["status"], r["material"]["available"]) == ("rejected", 100)

    second = client.post(f"/admin/materials/{m['id']}/distributions", json={"teamId": "t-rx", "quantity": 40}, headers=mia).json()["distributions"][0]
    r = client.post(f"/admin/materials/{m['id']}/distributions/{second['id']}/cancel", headers=mia).json()
    assert (r["distributions"][0]["status"], r["material"]["available"]) == ("cancelled", 100)
    assert apps.sent[-1][2]["state"] == "cancelled"


def test_designs_are_checked_and_an_outage_is_kept_not_raised(app, client, apps):
    mia = sign_in(client, "mia@example.com")
    m = client.post("/admin/materials", json={"title": "Poster", "kind": "Poster"}, headers=mia).json()["material"]
    assert client.post("/admin/materials", json={"title": "Pen", "kind": "Ballpen"}, headers=mia).status_code == 422
    assert upload(client, m["id"], mia, data=b"not a design").status_code == 422
    assert upload(client, m["id"], mia, data=b"%PDF" + b"x" * (3 * 1024 * 1024)).status_code == 422

    # Uploading again before sending replaces the draft rather than adding a version.
    upload(client, m["id"], mia)
    r = upload(client, m["id"], mia, data=b"\x89PNG design")
    assert [v["number"] for v in r.json()["versions"]] == [1]
    assert client.get(f"/admin/materials/{m['id']}/versions/1/file", headers=mia).content == b"\x89PNG design"

    apps.down = True
    assert client.post(f"/admin/materials/{m['id']}/submit", headers=mia).status_code == 503
    apps.down = False
    client.post(f"/admin/materials/{m['id']}/submit", headers=mia)
    apps.down = True
    expire(app)
    r = client.get(f"/admin/materials/{m['id']}", headers=mia)
    assert r.status_code == 200
    assert r.json()["versions"][0]["syncError"] == "Pharmacy can't be reached right now."


def test_who_may_do_what(app, client, apps):
    mia = sign_in(client, "mia@example.com")
    auditor = sign_in(client, "audit@example.com")
    assert client.get("/admin/materials", headers=auditor).status_code == 200
    assert client.post("/admin/materials", json={"title": "Poster", "kind": "Poster"}, headers=auditor).status_code == 403
    assert client.get("/admin/vehicles", headers=mia).status_code == 403  # the marketing assistant sees only materials
    m = client.post("/admin/materials", json={"title": "Poster", "kind": "Poster"}, headers=mia).json()["material"]
    assert client.delete(f"/admin/materials/{m['id']}", headers=mia).status_code == 403
    assert client.delete(f"/admin/materials/{m['id']}", headers=sign_in(client)).status_code == 204


def test_not_connected_says_so(app, client):
    with app.state.sessions() as db:
        db.add(User(email="mia@example.com", full_name="Mia Marketing", password_hash=hash_password(PASSWORD), role_id=ROLE_MARKETING_ID))
        db.commit()
    mia = sign_in(client, "mia@example.com")
    r = client.get("/admin/materials", headers=mia).json()
    assert r["linked"] == {"pharmacy": False, "crm": False}
    m = client.post("/admin/materials", json={"title": "Poster", "kind": "Poster"}, headers=mia).json()["material"]
    upload(client, m["id"], mia)
    r = client.post(f"/admin/materials/{m['id']}/submit", headers=mia)
    assert r.status_code == 503 and "not connected to Pharmacy" in r.json()["detail"]


def test_details_and_proof_photos(app, client, apps):
    mia = sign_in(client, "mia@example.com")
    asst = sign_in(client, "asst@example.com")
    m = client.post(
        "/admin/materials",
        json={"title": "Glucare poster", "kind": "Poster", "quantity": 300, "specs": "A2, glossy", "neededBy": "2026-11-15", "budget": 15000},
        headers=mia,
    ).json()["material"]
    assert (m["quantity"], m["specs"], m["neededBy"], m["budget"]) == (300, "A2, glossy", "2026-11-15", 15000)
    upload(client, m["id"], mia)
    client.post(f"/admin/materials/{m['id']}/submit", headers=mia)
    apps.reviews[apps.sent[-1][2]["sourceId"]]["outcome"] = "approved"
    expire(app)
    client.get(f"/admin/materials/{m['id']}", headers=mia)
    run = client.post(f"/admin/materials/{m['id']}/productions", json={"quantity": 300}, headers=asst).json()["productions"][0]

    # Received with a photo of the delivery; a text file isn't taken as proof.
    bad = client.post(f"/admin/materials/{m['id']}/productions/{run['id']}/received", data={"receivedOn": "2026-10-20"}, files={"proof": ("note.txt", b"hello", "text/plain")}, headers=asst)
    assert bad.status_code == 422
    photo = JPEG + b" photo"
    r = client.post(f"/admin/materials/{m['id']}/productions/{run['id']}/received", data={"receivedOn": "2026-10-20"}, files={"proof": ("delivery.jpg", photo, "image/jpeg")}, headers=asst).json()
    run = r["productions"][0]
    assert (run["receivedOn"], run["proof"]["name"]) == ("2026-10-20", "delivery.jpg")
    assert client.get(f"/admin/materials/{m['id']}/proofs/{run['proof']['ref']}", headers=mia).content == photo
    assert client.get(f"/admin/materials/{m['id']}/proofs/nope", headers=mia).status_code == 404

    d = client.post(f"/admin/materials/{m['id']}/distributions", json={"teamId": "t-rx", "quantity": 100}, headers=mia).json()["distributions"][0]
    apps.requests[d["id"]]["outcome"] = "approved"
    expire(app)
    client.get(f"/admin/materials/{m['id']}", headers=mia)
    r = client.post(f"/admin/materials/{m['id']}/distributions/{d['id']}/distributed", files={"proof": ("receipt.pdf", b"%PDF signed", "application/pdf")}, headers=mia).json()
    assert r["distributions"][0]["proof"]["name"] == "receipt.pdf"
    assert any("proof attached" in h["text"] for h in r["history"])


def test_a_vehicle_is_a_car_or_a_motorcycle(app, client):
    asst = sign_in(client, "asst@example.com")
    bike = client.post("/admin/vehicles", json={"name": "Honda Click 125-i", "plate": "167UDW"}, headers=asst).json()
    car = client.post("/admin/vehicles", json={"name": "Toyota Wigo", "plate": "NIQ 2383"}, headers=asst).json()
    assert (bike["kind"], car["kind"]) == ("motorcycle", "car")  # worked out from the plate
    changed = client.patch(f"/admin/vehicles/{car['id']}", json={"name": "Toyota Wigo", "plate": "NIQ 2383", "kind": "motorcycle"}, headers=asst).json()
    assert changed["kind"] == "motorcycle"  # set by hand, it stands


def test_urgency_comes_from_its_own_dates_and_stock(app, client, apps):
    from datetime import date, timedelta

    from app.models import PromoVersion

    mia = sign_in(client, "mia@example.com")
    asst = sign_in(client, "asst@example.com")
    soon = (date.today() + timedelta(days=5)).isoformat()
    m = client.post("/admin/materials", json={"title": "Flu season poster", "kind": "Poster", "neededBy": soon}, headers=mia).json()["material"]
    later = client.post("/admin/materials", json={"title": "Calendar 2027", "kind": "Calendar"}, headers=mia).json()["material"]
    u = m["urgency"]
    assert (u["neededIn"], u["tier"]) == (5, "urgent")
    assert u["next"] == "Upload the design and submit it for review today. It's needed in 5 days."
    assert later["urgency"]["tier"] == "none"  # no date needed: nothing made up

    # The most pressing first in the list, and on the overview for the executive office.
    assert [i["title"] for i in client.get("/admin/materials", headers=mia).json()["items"]][0] == "Flu season poster"
    dash = client.get("/admin/dashboard", headers=sign_in(client)).json()
    assert any(h["entityType"] == "material" and h["daysRemaining"] == 5 for h in dash["countdownHighlights"])

    # Waiting on the pharmacist for four days.
    upload(client, m["id"], mia)
    client.post(f"/admin/materials/{m['id']}/submit", headers=mia)
    with app.state.sessions() as db:
        v = db.query(PromoVersion).filter_by(material_id=m["id"]).one()
        v.sent_at = v.sent_at - timedelta(days=4)
        db.commit()
    u = client.get(f"/admin/materials/{m['id']}", headers=mia).json()["material"]["urgency"]
    assert u["waiting"] == {"on": "pharmacist", "days": 4}
    assert "Waiting 4 days" in u["next"]

    # In stock, the countdown stops; little left is flagged.
    apps.reviews[apps.sent[-1][2]["sourceId"]]["outcome"] = "approved"
    expire(app)
    client.get(f"/admin/materials/{m['id']}", headers=mia)
    run = client.post(f"/admin/materials/{m['id']}/productions", json={"quantity": 100}, headers=asst).json()["productions"][0]
    r = client.post(f"/admin/materials/{m['id']}/productions/{run['id']}/received", data={}, headers=asst).json()["material"]
    assert (r["urgency"]["neededIn"], r["urgency"]["lowStock"]) == (None, False)
    r = client.post(f"/admin/materials/{m['id']}/distributions", json={"teamId": "t-rx", "quantity": 92}, headers=mia).json()["material"]
    assert (r["available"], r["urgency"]["lowStock"]) == (8, True)
    assert r["urgency"]["next"].startswith("Only 8 free to give out")
