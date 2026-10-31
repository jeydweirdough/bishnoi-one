"""A company must be registered on the platform to use the CRM (app/company.py):
active, and given the CRM. The platform is stood in for with a signed company pass."""

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import company
from tests.conftest import PASSWORD, sign_in

KEY = Ed25519PrivateKey.generate()
PUBLIC = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def company_pass(status="active", granted=True, slug="getmeds", key=KEY, exp=None, **more) -> str:
    head = b64(json.dumps({"alg": "EdDSA", "typ": "JWT"}).encode())
    body = b64(json.dumps({
        "iss": "bishnoi-platform", "aud": "crm", "kind": "company", "company": "co-1", "slug": slug,
        "companyName": "GetMeds", "status": status, "granted": granted, "exp": exp or int(time.time()) + 3600, **more,
    }).encode())
    return f"{head}.{body}.{b64(key.sign(f'{head}.{body}'.encode()))}"


class Answer:
    def __init__(self, status_code, data=None):
        self.status_code, self.data = status_code, data

    def json(self):
        return self.data


@pytest.fixture
def platform(app, monkeypatch):
    """The CRM linked to GetMeds on a stand-in platform; set `answer` to change what it says."""
    company.forget()
    app.state.settings = app.state.settings.model_copy(update={"platform_api_url": "https://platform.test", "platform_public_key": PUBLIC})
    state = {"answer": Answer(200, {"pass": company_pass()}), "asked": 0}

    def get(url, params=None, timeout=None):
        state["asked"] += 1
        if isinstance(state["answer"], Exception):
            raise state["answer"]
        return state["answer"]

    monkeypatch.setattr(company.httpx, "get", get)
    yield state
    company.forget()


def test_a_registered_company_signs_in(client, platform):
    assert sign_in(client).status_code == 200
    assert client.get("/auth/company").json() == {"ok": True, "message": "GetMeds", "name": "GetMeds", "slug": "getmeds"}
    # Asked once, then kept for the hour the pass lasts.
    sign_in(client)
    assert platform["asked"] == 1


@pytest.mark.parametrize(
    ("answer", "says", "code"),
    [
        (Answer(404), "isn't registered on Bishnoi One Platform", 403),
        (Answer(200, {"pass": company_pass(status="suspended")}), "is suspended", 403),
        (Answer(200, {"pass": company_pass(granted=False)}), "isn't set up to use the CRM", 403),
        # A pass that doesn't verify is the server's setup, not a no: a wait (503).
        (Answer(200, {"pass": company_pass(key=Ed25519PrivateKey.generate())}), "isn't available right now", 503),
        (Answer(200, {"pass": company_pass(slug="another")}), "isn't available right now", 503),
    ],
)
def test_no_sign_in_without_a_registered_company(client, platform, answer, says, code):
    platform["answer"] = answer
    r = sign_in(client)
    assert r.status_code == code and says in r.json()["detail"]


def test_a_suspended_company_is_stopped_on_its_next_click(app, client, platform):
    headers = {"Authorization": f"Bearer {sign_in(client).json()['accessToken']}"}
    assert client.get("/companies", headers=headers).status_code == 200
    company.forget(kept=True, settings=app.state.settings)
    platform["answer"] = Answer(200, {"pass": company_pass(status="suspended")})
    assert client.get("/companies", headers=headers).status_code == 403


def test_an_outage_or_a_restart_keeps_the_kept_pass(app, client, platform):
    import httpx

    assert sign_in(client).status_code == 200
    company.forget()  # a restart: nothing in memory; the platform is unreachable
    platform["answer"] = httpx.ConnectError("down")
    asked = platform["asked"]
    assert sign_in(client, password=PASSWORD).status_code == 200
    assert platform["asked"] == asked  # the kept pass, read from the database: nobody waited
    company.forget(kept=True, settings=app.state.settings)  # and with no pass to fall back on: a wait, not a no
    r = sign_in(client)
    assert r.status_code == 503 and r.headers["retry-after"] == "30" and "isn't available right now" in r.json()["detail"]


def test_production_needs_the_platform_and_a_company(app, client, caplog):
    company.forget()
    app.state.settings = app.state.settings.model_copy(update={"environment": "production"})
    try:
        r = sign_in(client)  # not saying which company: there's no default in production
        assert r.status_code == 400 and "Say which company" in r.json()["detail"]
        r = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}, headers={"X-Bishnoi-Company": "getmeds"})
        # Not the person's to fix: they're told plainly, and the setting is named in the server's log.
        assert r.status_code == 503 and "isn't available right now" in r.json()["detail"] and "PLATFORM" not in r.json()["detail"]
        assert "PLATFORM_API_URL" in caplog.text
    finally:
        app.state.settings = app.state.settings.model_copy(update={"environment": "development"})


def test_on_this_computer_only_the_dev_companies(client):
    r = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}, headers={"X-Bishnoi-Company": "nowhere"})
    assert r.status_code == 403 and "no company" in r.json()["detail"]
    assert client.get("/auth/company", headers={"X-Bishnoi-Company": "Not A Slug!"}).status_code == 400


def test_a_paused_company_is_told_until_when(client, platform):
    platform["answer"] = Answer(200, {"pass": company_pass(status="paused", pausedUntil="Mon 12 Oct 2026, 8:00 AM")})
    r = sign_in(client)
    assert r.status_code == 403 and "paused until Mon 12 Oct 2026, 8:00 AM" in r.json()["detail"]


def keep(app, token, at):
    from app import platform_connect

    platform_connect.write_value(app.state.settings, "company_pass:getmeds", json.dumps({"pass": token, "at": at}))
    company.forget()


def test_a_kept_pass_over_an_hour_old_is_used_and_renewed_meanwhile(app, client, platform):
    keep(app, company_pass(), time.time() - 7200)
    platform["answer"] = Answer(200, {"pass": company_pass(status="suspended")})
    assert sign_in(client).status_code == 200  # not kept waiting for the platform
    for _ in range(50):  # the fresh pass arrives in the background
        if company._last["getmeds"].message.endswith("Ask your Bishnoi One administrator."):
            break
        time.sleep(0.05)
    assert sign_in(client).status_code == 403


def test_a_pass_that_has_run_out_is_no_use_in_an_outage(app, client, platform):
    import httpx

    keep(app, company_pass(exp=int(time.time()) - 600), time.time() - 7200)
    platform["answer"] = httpx.ConnectError("down")
    assert sign_in(client).status_code == 503


def test_the_platform_tells_us_at_once_and_nobody_else_can(app, client, platform):
    headers = {"Authorization": f"Bearer {sign_in(client).json()['accessToken']}"}
    newer = int(time.time()) + 5
    # Genuine, newer: taken, and the next click is refused.
    assert client.post("/platform/company", json={"pass": company_pass(status="suspended", iat=newer)}).status_code == 204
    assert client.get("/companies", headers=headers).status_code == 403
    # The older pass sent again (a replay) changes nothing, and looks like no address at all.
    r = client.post("/platform/company", json={"pass": company_pass(status="active", iat=newer - 60)})
    assert (r.status_code, r.json()) == (404, {"detail": "Not Found"})
    assert client.get("/companies", headers=headers).status_code == 403
    # Not signed by the platform, not for the CRM, or not a pass: the same.
    for body in ({"pass": company_pass(key=Ed25519PrivateKey.generate(), iat=newer + 10)}, {"pass": company_pass(aud="inventory", iat=newer + 10)}, {"pass": "x.y.z"}, {"nothing": 1}):
        r = client.post("/platform/company", json=body)
        assert (r.status_code, r.json()) == (404, {"detail": "Not Found"})
    # Any other way of asking, the same as an address that doesn't exist; and it isn't in the API's map.
    assert client.get("/platform/company").json() == client.get("/no/such/address").json()
    assert client.get("/platform/company").status_code == 404
    assert "/platform/company" not in client.get("/openapi.json").text
    # Reactivated on the platform: back at once.
    assert client.post("/platform/company", json={"pass": company_pass(iat=newer + 20)}).status_code == 204
    assert client.get("/companies", headers=headers).status_code == 200


def test_the_company_profile_on_bishnoi_one_is_the_crms(app, client, platform):
    """Connected, the CRM shows its company as the Admin Console's Company profile has it, puts that on
    quotes, and keeps only the quote settings of its own (2026-10-31)."""
    profile = {"name": "Getmeds Philippines Inc.", "legalName": "Getmeds Philippines Inc.", "currency": "PHP", "locale": "en-US",
               "timezone": "Asia/Manila", "address": "Unit 305, Vatican Bldg.", "tin": "605-059-166-00000", "phone": "+63 2 8123 4567"}
    platform["answer"] = Answer(200, {"pass": company_pass(profile=profile)})
    # Signed in with a password while not connected (connected, only Bishnoi One signs people in), then connected again.
    connected = app.state.settings
    app.state.settings = connected.model_copy(update={"platform_api_url": None})
    headers = {"Authorization": f"Bearer {sign_in(client).json()['accessToken']}"}
    app.state.settings = connected
    shown = client.get("/admin/company-settings", headers=headers).json()
    assert shown["onPlatform"] is True
    assert (shown["orgName"], shown["locale"], shown["companyAddress"], shown["companyTin"], shown["companyContact"]) == (
        "Getmeds Philippines Inc.", "en-US", "Unit 305, Vatican Bldg.", "605-059-166-00000", "+63 2 8123 4567")
    assert client.get("/auth/me", headers=headers).json()["org"]["name"] == "Getmeds Philippines Inc."
    assert client.get("/quote-letterhead", headers=headers).json() == {
        "name": "Getmeds Philippines Inc.", "address": "Unit 305, Vatican Bldg.", "tin": "605-059-166-00000", "contact": "+63 2 8123 4567"}
    # Changed only on the Admin Console; sent back as shown, the quote settings still save.
    refused = client.patch("/admin/company-settings", json={"companyTin": "000-000-000-000"}, headers=headers)
    assert refused.status_code == 409 and "Company profile" in refused.json()["detail"]
    saved = client.patch("/admin/company-settings", json={"orgName": "Getmeds Philippines Inc.", "quotePrefix": "GPI", "quoteValidDays": 15}, headers=headers)
    assert saved.status_code == 200, saved.text
    assert (saved.json()["quotePrefix"], saved.json()["quoteValidDays"], saved.json()["orgName"]) == ("GPI", 15, "Getmeds Philippines Inc.")
