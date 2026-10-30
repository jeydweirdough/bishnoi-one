"""Data clean-up and the recycle bin in Executive Admin (2026-10-30, app/recycle_bin.py)."""

from tests.test_record_permissions import TICKET, client, who  # noqa: F401 (fixture)


def test_a_ticket_goes_to_the_bin_with_its_updates_and_comes_back(client):  # noqa: F811
    admin, audit = who(client, "admin"), who(client, "audit")
    assert client.get("/data-cleanup/kinds", headers=audit).status_code == 403
    t = client.post("/admin/tickets", json=TICKET, headers=admin).json()
    r = client.post("/data-cleanup/kinds/tickets/delete", json={"ids": [t["id"]]}, headers=admin)
    assert r.status_code == 200, r.text
    assert client.get(f"/admin/tickets/{t['id']}", headers=admin).status_code == 404
    entry = client.get("/data-cleanup/bin", headers=admin).json()["items"][0]
    assert entry["label"] == "Aircon not cooling"
    assert client.post(f"/data-cleanup/bin/{entry['id']}/restore", headers=admin).status_code == 200
    assert client.get(f"/admin/tickets/{t['id']}", headers=admin).status_code == 200
