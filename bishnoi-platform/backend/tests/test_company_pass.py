"""A company pass (GET /public/company-pass): how an application knows its
company is registered here, active, and may use it. Signed, so the
application can trust it with the platform's public key alone."""

from app import passes
from app.config import get_settings
from tests.conftest import make_company
from tests.test_identity import claims_of


def public_key(app) -> str:
    return passes.public_key(app.state.settings if hasattr(app.state, "settings") else get_settings())


def test_a_registered_company_gets_a_signed_pass(app, client, ana):
    company = make_company(client, ana, apps=("crm",))
    r = client.get(f"/public/company-pass?app=crm&company={company['slug']}")
    assert r.status_code == 200, r.text
    claims = claims_of(r.json()["pass"], public_key(app))
    assert (claims["aud"], claims["kind"], claims["slug"], claims["status"], claims["granted"]) == ("crm", "company", company["slug"], "active", True)
    # Registered, but not given this application.
    other = claims_of(client.get(f"/public/company-pass?app=pharmacy&company={company['slug']}").json()["pass"], public_key(app))
    assert other["granted"] is False


def test_an_unknown_company_gets_none(client):
    assert client.get("/public/company-pass?app=crm&company=nobody").status_code == 404
