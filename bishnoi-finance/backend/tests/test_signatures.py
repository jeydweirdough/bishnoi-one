"""E-signatures (decided 2026-10-22: Plans/Plan - E-signatures): each person sets their
own (password, or a recent Bishnoi One sign-in); it's placed by their own step on the
journal voucher (prepared, approved) and the liquidation report (reviewed, settled), with
a fingerprint; a replaced one leaves what it signed as it was; an administrator can only
remove one."""

import base64
import struct
import zlib
from datetime import UTC, datetime, timedelta

import pytest

from app.models import SignInSession, User

from .test_auth import PASSWORD, bearer, sign_in
from .test_dashboard import BIR, HEAD, person
from .test_funds import KEY, approved, categories, check_all, release, spend
from .test_journal_approval import post
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)


def png(width: int = 60, height: int = 20, shade: int = 0) -> str:
    """A small black-on-transparent PNG, as the browser sends it (a data URL)."""
    row = b"\x00" + bytes([shade, shade, shade, 255]) * width
    raw = row * height
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    body = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(body).decode()


def set_mine(client, who, image=None, password=PASSWORD, method="drawn"):
    return client.put("/auth/signature", json={"image": image or png(), "method": method, "password": password}, headers=who)


@pytest.fixture
def malou(client, ana):
    return person(client, ana, "Finance Head", HEAD + ["journal.approve"])


@pytest.fixture
def rommel(client, ana):
    return person(client, ana, "BIR and Compliance", BIR)


def steps(client, who, kind, record_id):
    return client.get(f"/finance/signatures/{kind}/{record_id}", headers=who).json()["steps"]


def test_setting_your_signature_asks_for_your_password(client, ben):
    assert client.get("/auth/signature", headers=ben).json() == {"current": None, "confirmBy": "password", "recentSignIn": False}
    assert set_mine(client, ben, password=None).status_code == 422
    assert set_mine(client, ben, password="not it").status_code == 422
    r = set_mine(client, ben)
    assert r.status_code == 200 and r.json()["current"]["method"] == "drawn" and r.json()["current"]["image"].startswith("data:image/png;base64,")


def test_only_a_sensible_png_is_kept(client, ben):
    assert set_mine(client, ben, image="data:image/png;base64," + base64.b64encode(b"GIF89a not a png at all......").decode()).status_code == 422
    assert set_mine(client, ben, image=png(5000, 20)).status_code == 422  # far too wide
    assert set_mine(client, ben, image="not base64 !!").status_code == 422


def test_a_bishnoi_one_sign_in_confirms_by_being_recent(app, client, ana):
    with app.state.sessions() as db:
        u = db.query(User).filter_by(email="ben@example.com").one()
        u.platform_identity_id = "platform-ben"
        db.commit()
    ben = bearer(sign_in(client, "ben@example.com"))
    assert client.get("/auth/signature", headers=ben).json()["confirmBy"] == "recent_sign_in"
    assert set_mine(client, ben, password=None).status_code == 200  # just signed in
    with app.state.sessions() as db:
        # Signed in two hours ago (and the account older than that, so the session still holds).
        db.query(User).filter_by(email="ben@example.com").one().password_changed_at = datetime.now(UTC) - timedelta(hours=3)
        for s in db.query(SignInSession).all():
            s.created_at = datetime.now(UTC) - timedelta(hours=2)
        db.commit()
    r = set_mine(client, ben, password=None)
    assert r.status_code == 409 and "sign in again" in r.json()["detail"]


def test_each_step_places_its_own_signature_and_keeps_it(client, malou, rommel):
    assert set_mine(client, rommel, image=png(shade=1)).status_code == 200
    assert set_mine(client, malou, image=png(shade=2)).status_code == 200
    e = post(client, rommel)
    client.post(f"/finance/ledger/entries/{e['id']}/approve", headers=malou)
    signed = steps(client, rommel, "journal_entry", e["id"])
    assert [(s["label"], s["name"], s["role"]) for s in signed] == [("Prepared by", "BIR and Compliance", "BIR and Compliance"), ("Approved by", "Finance Head", "Finance Head")]
    assert signed[0]["image"] == png(shade=1) and signed[1]["image"] == png(shade=2) and len(signed[0]["ref"]) == 12
    # Malou changes her signature later: what she already signed keeps the old one.
    set_mine(client, malou, image=png(shade=3), method="uploaded")
    assert steps(client, rommel, "journal_entry", e["id"])[1]["image"] == png(shade=2)


def test_a_step_without_a_signature_set_still_says_who(client, malou, rommel):
    e = post(client, rommel)
    signed = steps(client, rommel, "journal_entry", e["id"])
    assert signed[0]["name"] == "BIR and Compliance" and signed[0]["image"] is None


def test_the_liquidation_report_is_signed_on_review_and_settlement(client, ana, ben, malou):
    set_mine(client, malou)
    set_mine(client, ben, image=png(shade=4))
    req = release(client, ben, approved(client)["id"])
    spend(client, 320000, categories(client)["Food"])
    sent = client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico Santos"}, headers=KEY).json()
    done = check_all(client, malou, sent)
    assert done["status"] == "to_return"
    client.post(f"/finance/funds/{req['id']}/returned", json={"amountCentavos": done["returnDueCentavos"]}, headers=ben)
    signed = steps(client, malou, "fund_request", req["id"])
    assert [(s["label"], s["name"]) for s in signed] == [("Reviewed by", "Finance Head"), ("Settled by", "Ben Cruz")]
    assert signed[1]["image"] == png(shade=4)


def test_only_those_who_may_see_the_document_see_its_signatures(client, ana, rommel):
    e = post(client, rommel)
    outsider = person(client, ana, "Prices only", ["dashboard.view", "prices.view"])
    assert client.get(f"/finance/signatures/journal_entry/{e['id']}", headers=outsider).status_code == 403
    assert client.get("/finance/signatures/payroll/x", headers=rommel).status_code == 404
    assert client.get("/finance/signatures/journal_entry/no-such", headers=rommel).status_code == 404


def test_an_administrator_can_only_remove_a_signature(client, ana, ben, rommel):
    set_mine(client, rommel)
    e = post(client, rommel)
    rid = next(u["id"] for u in client.get("/admin/users", headers=ana).json()["items"] if u["email"] == "bir.and.compliance@example.com")
    assert next(u for u in client.get("/admin/users", headers=ana).json()["items"] if u["id"] == rid)["hasSignature"] is True
    assert client.delete(f"/admin/users/{rid}/signature", headers=ben).status_code == 403
    assert client.delete(f"/admin/users/{rid}/signature", headers=ana).status_code == 204
    assert client.get("/auth/signature", headers=rommel).json()["current"] is None
    assert steps(client, rommel, "journal_entry", e["id"])[0]["image"] is not None  # what it signed keeps it
    # There's no way for an administrator to set it: only the person's own /auth/signature.
    assert client.put(f"/admin/users/{rid}/signature", json={}, headers=ana).status_code in (404, 405)


def test_removing_your_own_needs_your_password_too(client, ben):
    set_mine(client, ben)
    assert client.post("/auth/signature/remove", json={}, headers=ben).status_code == 422
    assert client.post("/auth/signature/remove", json={"password": PASSWORD}, headers=ben).json()["current"] is None
