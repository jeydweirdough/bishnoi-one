"""One e-signature per person (feature plan step 10): Finance signs with the person's Bishnoi One signature
when they haven't set one here, and keeps its own copy."""

import base64
import struct

import httpx
from pydantic import SecretStr
from sqlalchemy import select

from app import business_events, signatures
from app.models import Signature, User
from .test_tax_api import ana, app, client  # noqa: F401 (fixtures)


def png(width=200) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, 60) + b"\x08\x06\x00\x00\x00" + b"\x00" * 40


class Answer:
    def __init__(self, status_code, body=None):
        self.status_code, self._body = status_code, body

    def json(self):
        return self._body


def test_signing_uses_the_platform_signature_and_follows_its_changes(app, client, ana, monkeypatch):  # noqa: F811
    on_platform = {"image": png()}
    monkeypatch.setattr(httpx, "get", lambda url, params=None, headers=None, timeout=None:
                        Answer(200, {"image": "data:image/png;base64," + base64.b64encode(on_platform["image"]).decode()}) if on_platform["image"] else Answer(404))
    s = app.state.settings
    s.platform_api_url, s.platform_app_key = "https://platform.example.com", SecretStr("finance-key")
    business_events._state["settings"] = s
    try:
        with app.state.sessions() as db:
            user = db.scalar(select(User).where(User.email == "ana@example.com"))
            user.platform_identity_id = "identity-ana"
            first = signatures.sign(db, user, "journal_entry", "j1", "prepared", {"n": 1})
            db.flush()
            held = db.get(Signature, first.signature_id)
            assert held.method == "platform" and held.image == png()
            again = signatures.sign(db, user, "journal_entry", "j2", "prepared", {"n": 2})
            assert again.signature_id == first.signature_id  # unchanged: the same copy
            on_platform["image"] = png(300)  # changed on the Platform
            third = signatures.sign(db, user, "journal_entry", "j3", "prepared", {"n": 3})
            assert third.signature_id != first.signature_id and db.get(Signature, first.signature_id).replaced_at is not None
            on_platform["image"] = None  # removed there
            assert signatures.sign(db, user, "journal_entry", "j4", "prepared", {"n": 4}).signature_id is None
    finally:
        s.platform_api_url, s.platform_app_key = None, None
