"""A company's outside services (Zoho Books, the email providers) are filled in
here, and given only to the applications that use them (app/services.py)."""

from app import services
from app.models import ServiceConnection
from tests.conftest import make_company
from tests.test_connections import connect

ZOHO = {
    "data_centre": "com",
    "organization_id": "60012345",
    "client_id": "1000.ABC",
    "client_secret": "client-secret-12345678",
    "refresh_token": "1000.refresh-token-abcdefgh",
}


def zoho(client, headers, company_id) -> dict:
    return next(s for s in client.get(f"/platform/companies/{company_id}/services", headers=headers).json()["services"] if s["key"] == "zoho_books")


def test_secrets_are_kept_encrypted_and_never_come_back(app, client, ana, ben):
    getmeds = make_company(client, ana)
    r = client.put(f"/platform/companies/{getmeds['id']}/services/zoho_books", json={"values": ZOHO}, headers=ana)
    assert r.status_code == 200, r.text
    secret = next(d for d in r.json()["details"] if d["key"] == "client_secret")
    assert secret == {**secret, "saved": True, "ending": "5678"} and "value" not in secret
    assert "client-secret" not in r.text and "refresh-token" not in r.text
    with app.state.sessions() as db:
        row = db.query(ServiceConnection).one()
        assert "client-secret" not in (row.secrets or "") and services.unseal(app.state.settings, row.secrets)["client_secret"] == ZOHO["client_secret"]
    # Support sees it, but can't change it.
    assert zoho(client, ben, getmeds["id"])["missing"] == []
    assert client.put(f"/platform/companies/{getmeds['id']}/services/zoho_books", json={"enabled": True}, headers=ben).status_code == 403
    # Switching on needs every required detail; switched on, one can't be removed.
    on = client.put(f"/platform/companies/{getmeds['id']}/services/zoho_books", json={"enabled": True}, headers=ana).json()
    assert on["enabled"] is True
    r = client.put(f"/platform/companies/{getmeds['id']}/services/zoho_books", json={"values": {"refresh_token": ""}}, headers=ana)
    assert r.status_code == 409
    r = client.put(f"/platform/companies/{getmeds['id']}/services/zoho_books", json={"values": {"data_centre": "mars"}}, headers=ana)
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "values", "data_centre"]


def test_testing_tries_the_details_on_zoho(client, ana, monkeypatch):
    getmeds = make_company(client, ana)
    client.put(f"/platform/companies/{getmeds['id']}/services/zoho_books", json={"values": ZOHO}, headers=ana)
    monkeypatch.setitem(services.CHECKS, "zoho_books", lambda details: f"Connected to {details['organization_id']}.")
    ok = client.post(f"/platform/companies/{getmeds['id']}/services/zoho_books/check", headers=ana).json()
    assert ok["check"]["ok"] is True and ok["check"]["message"] == "Connected to 60012345."

    def refused(details):
        raise services.CheckFailed("Zoho didn't accept them.")

    monkeypatch.setitem(services.CHECKS, "zoho_books", refused)
    assert client.post(f"/platform/companies/{getmeds['id']}/services/zoho_books/check", headers=ana).json()["check"]["ok"] is False
    # New details: the last test was of the old ones.
    assert client.put(f"/platform/companies/{getmeds['id']}/services/zoho_books", json={"values": {"client_id": "1000.NEW"}}, headers=ana).json()["check"] is None


def test_an_application_is_given_its_companys_services(client, ana):
    getmeds = make_company(client, ana, apps=("crm",))
    other = make_company(client, ana, name="Northwind", apps=("inventory",))
    crm = connect(client, ana, "crm")
    inventory = connect(client, ana, "inventory")
    gmail = {"client_id": "gmail-client", "client_secret": "gmail-secret-123456"}
    client.put(f"/platform/companies/{getmeds['id']}/services/gmail", json={"values": gmail, "enabled": True}, headers=ana)
    client.put(f"/platform/companies/{getmeds['id']}/services/zoho_books", json={"values": ZOHO}, headers=ana)  # filled in, but off

    asked = client.get("/connect/services", params={"company": getmeds["slug"]}, headers={"X-Bishnoi-App-Key": crm})
    assert asked.status_code == 200
    assert asked.json()["services"] == {"gmail": gmail}
    # Another application isn't given the CRM's services; a company without the CRM gives nothing.
    assert client.get("/connect/services", params={"company": getmeds["slug"]}, headers={"X-Bishnoi-App-Key": inventory}).json()["services"] == {}
    assert client.get("/connect/services", params={"company": other["slug"]}, headers={"X-Bishnoi-App-Key": crm}).json()["services"] == {}
    # No connect key, no answer.
    assert client.get("/connect/services", params={"company": getmeds["slug"]}).status_code == 401


def test_an_application_keeps_its_data_key_through_new_connect_keys(client, ana):
    first = client.get("/connect/links", headers={"X-Bishnoi-App-Key": connect(client, ana, "crm")}).json()["dataKey"]
    again = client.get("/connect/links", headers={"X-Bishnoi-App-Key": connect(client, ana, "crm")}).json()["dataKey"]
    assert first and first == again
    assert client.get("/connect/links", headers={"X-Bishnoi-App-Key": connect(client, ana, "inventory")}).json()["dataKey"] != first
