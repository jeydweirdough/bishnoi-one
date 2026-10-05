"""Settings → Connections: administrators keep the details for Zoho Books;
secrets are encrypted, never shown again, and testing tries them on Zoho."""

from app import connections
from app.models import Connection

ZOHO = {
    "data_centre": "com",
    "organization_id": "60012345",
    "client_id": "1000.ABC",
    "client_secret": "s3cret-client-value",
    "refresh_token": "1000.refresh-token-value",
}


def details(conn) -> dict:
    return {d["key"]: d for d in conn["details"]}


def test_only_administrators_see_connections(client, ana, ben):
    assert client.get("/admin/connections", headers=ben).status_code == 403
    zoho = next(c for c in client.get("/admin/connections", headers=ana).json() if c["key"] == "zoho_books")
    assert (zoho["key"], zoho["name"], zoho["enabled"], zoho["check"]) == ("zoho_books", "Zoho Books", False, None)
    assert "Organization ID" in zoho["missing"] and details(zoho)["client_secret"]["saved"] is False


def test_secrets_are_kept_encrypted_and_never_come_back(app, client, ana):
    saved = client.put("/admin/connections/zoho_books", json={"values": ZOHO}, headers=ana).json()
    d = details(saved)
    assert d["organization_id"]["value"] == "60012345" and saved["missing"] == []
    assert (d["client_secret"]["saved"], d["client_secret"]["ending"], "value" in d["client_secret"]) == (True, "alue", False)
    assert "s3cret" not in str(saved)
    with app.state.sessions() as db:
        row = db.get(Connection, "zoho_books")
        assert "s3cret" not in (row.secrets or "") and "client_secret" not in row.values
    # Leaving a secret out keeps it; sending it empty removes it.
    again = client.put("/admin/connections/zoho_books", json={"values": {"organization_id": "60099999"}}, headers=ana).json()
    assert details(again)["refresh_token"]["saved"] and details(again)["organization_id"]["value"] == "60099999"
    cleared = client.put("/admin/connections/zoho_books", json={"values": {"client_secret": ""}}, headers=ana).json()
    assert details(cleared)["client_secret"]["saved"] is False and cleared["missing"] == ["Client secret"]
    # The audit log names what changed, never the values.
    log = client.get("/admin/audit?action=connection.", headers=ana).json()
    assert "s3cret" not in str(log)


def test_switching_on_needs_every_required_detail(client, ana):
    r = client.put("/admin/connections/zoho_books", json={"values": {"organization_id": "1"}, "enabled": True}, headers=ana)
    assert r.status_code == 409 and "Client ID" in r.json()["detail"]
    on = client.put("/admin/connections/zoho_books", json={"values": ZOHO, "enabled": True}, headers=ana).json()
    assert on["enabled"] is True
    r = client.put("/admin/connections/zoho_books", json={"values": {"refresh_token": ""}}, headers=ana)
    assert r.status_code == 409 and "Refresh token" in r.json()["detail"]
    r = client.put("/admin/connections/zoho_books", json={"values": {"data_centre": "mars"}}, headers=ana)
    assert r.status_code == 422


def test_testing_tries_the_details_on_zoho(client, ana, monkeypatch):
    client.put("/admin/connections/zoho_books", json={"values": ZOHO}, headers=ana)
    tried = {}

    def fake_zoho(given):
        tried.update(given)
        return "Connected to Getmeds Inc."

    monkeypatch.setitem(connections.CHECKS, "zoho_books", fake_zoho)
    ok = client.post("/admin/connections/zoho_books/check", headers=ana).json()
    assert ok["check"]["ok"] is True and ok["check"]["message"] == "Connected to Getmeds Inc."
    assert tried["client_secret"] == "s3cret-client-value" and tried["organization_id"] == "60012345"

    def refused(_):
        raise connections.CheckFailed("Zoho didn't accept the client ID, secret and refresh token (invalid_code).")

    monkeypatch.setitem(connections.CHECKS, "zoho_books", refused)
    bad = client.post("/admin/connections/zoho_books/check", headers=ana).json()
    assert bad["check"]["ok"] is False and "invalid_code" in bad["check"]["message"]
    # Changing a detail forgets the last test.
    assert client.put("/admin/connections/zoho_books", json={"values": {"client_id": "1000.NEW"}}, headers=ana).json()["check"] is None
