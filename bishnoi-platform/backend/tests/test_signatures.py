"""One e-signature per person, and the company's letterhead (feature plan step 10)."""

import base64
import struct

from tests.conftest import app_id
from tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)


def png(width=200, height=60) -> str:
    """Enough of a PNG for the checks: its signature and IHDR with the size."""
    body = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00" + b"\x00" * 40
    return "data:image/png;base64," + base64.b64encode(body).decode()


def test_a_person_sets_their_one_signature_with_their_password(client, ana, getmeds):
    jade = getmeds["jade"]["h"]
    assert client.get("/identity/signature", headers=jade).json()["has"] is False
    assert client.put("/identity/signature", json={"image": png(), "method": "drawn", "password": "wrong"}, headers=jade).status_code == 422
    assert client.put("/identity/signature", json={"image": png(5, 5), "method": "drawn", "password": "x"}, headers=jade).status_code == 422


def test_an_app_gets_the_current_signature_with_its_connect_key(app, client, ana, getmeds):
    from sqlalchemy import select

    from app import signatures
    from app.models import Account

    with app.state.sessions() as db:
        account = db.scalar(select(Account).where(Account.email == "jade@getmeds.test"))
        signatures.keep(db, account.id, base64.b64decode(png().split(",", 1)[1]), "drawn")
        db.commit()
    key = client.post(f"/platform/applications/{app_id(client, ana, 'crm')}/connect-key", headers=ana).json()["key"]
    jade = getmeds["jade"]["id"]
    r = client.get("/connect/signature", params={"identity": jade}, headers={"X-Bishnoi-App-Key": key})
    assert r.status_code == 200, r.text
    assert r.json()["image"].startswith("data:image/png;base64,") and len(r.json()["sha256"]) == 64
    assert client.get("/connect/signature", params={"identity": jade}, headers={"X-Bishnoi-App-Key": "nope"}).status_code == 401
    # Removed: the app is told there's none; the old one is kept for what it signed.
    with app.state.sessions() as db:
        signatures.retire(db, account.id)
        db.commit()
    assert client.get("/connect/signature", params={"identity": jade}, headers={"X-Bishnoi-App-Key": key}).status_code == 404
    assert client.get("/identity/signature", headers=getmeds["jade"]["h"]).json()["has"] is False


def test_the_company_letterhead(client, getmeds):
    h = getmeds["owner"]["h"]
    r = client.patch("/identity/company", json={"legalName": "GetMeds Philippines Inc.", "address": "Pasig City", "tin": "123-456-789-000", "logo": png()}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["company"]["logo"].startswith("data:image/png")
    assert client.patch("/identity/company", json={"logo": "data:image/gif;base64,R0lGODlhAQABAAAAACw="}, headers=h).status_code == 422
    # Any of the company's people reads it, to print.
    head = client.get("/identity/company/letterhead", headers=getmeds["jade"]["h"]).json()
    assert head["legalName"] == "GetMeds Philippines Inc." and head["tin"] == "123-456-789-000" and head["logo"]
    # Removing the logo and a field.
    client.patch("/identity/company", json={"logo": "", "tin": ""}, headers=h)
    head = client.get("/identity/company/letterhead", headers=getmeds["jade"]["h"]).json()
    assert head["logo"] is None and head["tin"] is None
