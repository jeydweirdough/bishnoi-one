"""The registration says exactly what an invoice still needs (fixed 2026-10-22: it said
only "name, TIN and address aren't all filled in", so a missing address went unnoticed)."""

from .test_invoices import SERIES, draft
from .test_tax_api import REGISTRATION, app, ana, ben, client  # noqa: F401 (fixtures)


def test_a_new_registration_misses_all_three(client, ben):
    p = client.get("/tax/setup", headers=ben).json()["profile"]
    assert p["missing"] == ["registered name", "TIN", "registered address"]
    assert p["missingSentence"] == "The company's registered name, TIN and registered address aren't filled in yet: every invoice needs them."


def test_only_the_address_missing_is_named(client, ana):
    p = client.put("/tax/profile", json={**REGISTRATION, "registeredAddress": None}, headers=ana).json()["profile"]
    assert p["missing"] == ["registered address"] and not p["complete"]
    assert p["missingSentence"] == "The company's registered address isn't filled in yet: every invoice needs it."
    # The invoice says the same, and won't issue until it's there.
    client.post("/finance/invoices/series", json=SERIES, headers=ana)
    d = draft(client, ana)
    assert d["computed"]["warnings"] == ["The company's registered address isn't filled in yet: every invoice needs it."]
    refused = client.post(f"/finance/invoices/{d['id']}/issue", json={}, headers=ana)
    assert refused.status_code == 409 and refused.json()["detail"].startswith("The company's registered address isn't filled in yet")
    # Filled in: nothing missing, and it issues.
    p = client.put("/tax/profile", json=REGISTRATION, headers=ana).json()["profile"]
    assert p["missing"] == [] and p["missingSentence"] == "" and p["complete"]
    assert client.post(f"/finance/invoices/{d['id']}/issue", json={}, headers=ana).status_code == 200
