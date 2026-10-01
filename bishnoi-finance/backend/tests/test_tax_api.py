"""Tax through the API: the registration, dated rate changes, working out a
sale, and other Nabhi apps asking with their key."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import User
from app.routers.auth import attempts
from app.security import hash_password

from .test_auth import PASSWORD, bearer, sign_in

CRM_KEY = "crm-key-that-is-long-enough-1234"


@pytest.fixture
def app(tmp_path):
    attempts.clear()
    settings = Settings(
        _env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        integration_keys=[f"crm:{CRM_KEY}"],
    )
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role="admin"))
        db.add(User(email="ben@example.com", full_name="Ben Cruz", password_hash=hash_password(PASSWORD)))
        db.commit()
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def ana(client):
    return bearer(sign_in(client))


@pytest.fixture
def ben(client):
    return bearer(sign_in(client, "ben@example.com"))


REGISTRATION = {
    "regime": "vat", "registeredName": "Nabhi Pharma Distribution Inc.", "tin": "123 456 789 00000",
    "registeredAddress": "123 Ayala Ave, Makati City", "pricesIncludeTax": True,
}


def line(price_pesos, **extra):
    return {"quantity": 1, "unitPriceCentavos": round(price_pesos * 100), **extra}


def summary(result) -> dict[str, int]:
    return {row["key"]: row["amountCentavos"] for row in result["summary"]}


def test_the_philippines_pack_is_set_up_on_start(client, ben):
    setup = client.get("/tax/setup", headers=ben).json()
    assert setup["profile"]["country"] == "PH" and setup["profile"]["regime"] == "vat" and not setup["profile"]["complete"]
    vat = next(c for c in setup["pack"]["codes"] if c["code"] == "PH_VAT12")
    assert vat["rateTodayBp"] == 1200
    pt = next(c for c in setup["pack"]["codes"] if c["code"] == "PH_PT")
    assert [r["rateBp"] for r in pt["rates"]] == [300, 100, 300]  # newest first
    assert setup["canEdit"] is False
    assert client.get("/tax/setup", headers=bearer(sign_in(client))).json()["canEdit"] is True


def test_only_admins_change_the_registration_and_the_tin_is_checked(client, ana, ben):
    assert client.put("/tax/profile", json=REGISTRATION, headers=ben).status_code == 403
    bad = client.put("/tax/profile", json={**REGISTRATION, "tin": "12345"}, headers=ana)
    assert bad.status_code == 422 and bad.json()["detail"][0]["loc"][-1] == "tin"
    profile = client.put("/tax/profile", json=REGISTRATION, headers=ana).json()["profile"]
    assert (profile["tin"], profile["branchCode"], profile["complete"]) == ("123-456-789", "00000", True)


def test_a_sale_as_its_invoice_shows_it(client, ana, ben):
    client.put("/tax/profile", json=REGISTRATION, headers=ana)
    r = client.post("/tax/compute", json={"lines": [line(112), line(100, category="exempt"), line(50, category="zero_rated")]}, headers=ben)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["document"] == "Sales Invoice" and got["seller"]["tin"] == "123-456-789-00000"
    assert summary(got) == {"taxable_sales": 10000, "tax": 1200, "zero_rated_sales": 5000, "exempt_sales": 10000}
    assert got["totalDueCentavos"] == 26200 and got["warnings"] == []


def test_a_senior_citizen_needs_an_id_and_gets_the_discount(client, ben):
    medicine = line(112, reliefEligible=True, description="Losartan 50mg")
    missing = client.post("/tax/compute", json={"treatment": "senior_citizen", "lines": [medicine]}, headers=ben)
    assert missing.status_code == 422 and missing.json()["detail"][0]["loc"][-1] == "idNumber"
    got = client.post(
        "/tax/compute",
        json={"treatment": "senior_citizen", "buyer": {"name": "Lola Nena", "idNumber": "OSCA-0042"}, "lines": [medicine]},
        headers=ben,
    ).json()
    assert got["relief"] == {"label": "Senior citizen discount (20%)", "amountCentavos": 2000}
    assert got["totalDueCentavos"] == 8000
    # Without the registration filled in, the answer says what's missing.
    assert got["warnings"]


def test_a_rate_change_applies_from_its_day(client, ana, ben):
    body = {"code": "PH_VAT12", "rateBp": 1500, "validFrom": "2030-01-01", "basis": "A made-up future law, for the test"}
    assert client.post("/tax/rates", json=body, headers=ben).status_code == 403
    setup = client.post("/tax/rates", json=body, headers=ana).json()
    vat = next(c for c in setup["pack"]["codes"] if c["code"] == "PH_VAT12")
    assert [(r["rateBp"], r["validFrom"], r["validTo"]) for r in vat["rates"]] == [(1500, "2030-01-01", None), (1200, "2006-02-01", "2029-12-31")]
    before = client.post("/tax/compute", json={"on": "2029-12-31", "pricesIncludeTax": False, "lines": [line(100)]}, headers=ben).json()
    after = client.post("/tax/compute", json={"on": "2030-01-01", "pricesIncludeTax": False, "lines": [line(100)]}, headers=ben).json()
    assert (before["totalDueCentavos"], after["totalDueCentavos"]) == (11200, 11500)
    # The same day twice, and a code with no rate, are refused.
    assert client.post("/tax/rates", json=body, headers=ana).status_code == 422
    assert client.post("/tax/rates", json={**body, "code": "PH_EXEMPT"}, headers=ana).status_code == 422


def test_a_non_vat_company(client, ana, ben):
    client.put("/tax/profile", json={**REGISTRATION, "regime": "non_vat"}, headers=ana)
    got = client.post("/tax/compute", json={"lines": [line(100)]}, headers=ben).json()
    assert summary(got) == {"non_taxable_sales": 10000}
    assert got["sellerTax"]["amountCentavos"] == 300 and got["notice"].startswith("THIS DOCUMENT IS NOT VALID")


def test_other_apps_ask_with_their_key(client):
    body = {"lines": [line(112)]}
    assert client.post("/integration/tax/compute", json=body).status_code == 401
    assert client.post("/integration/tax/compute", json=body, headers={"X-Nabhi-Key": "wrong"}).status_code == 401
    r = client.post("/integration/tax/compute", json=body, headers={"X-Nabhi-Key": CRM_KEY})
    assert r.status_code == 200 and r.json()["totalDueCentavos"] == 11200
    setup = client.get("/integration/tax/setup", headers={"X-Nabhi-Key": CRM_KEY}).json()
    assert {c["key"] for c in setup["pack"]["categories"]} == {"standard", "zero_rated", "exempt"} and setup["canEdit"] is False
