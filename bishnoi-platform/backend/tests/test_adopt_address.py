"""App addresses follow the platform's: an administrator opening the platform at
platform-<x> or platform.<x> moves every app still at this computer's address
(or the old pattern) to the same address with its own name."""

from tests.conftest import app_id


def addresses(client, headers) -> dict:
    return {a["key"]: a["appUrl"] for a in client.get("/platform/applications", headers=headers).json()["applications"]}


def test_apps_follow_the_platform_address(client, ana):
    crm = app_id(client, ana, "crm")
    client.patch(f"/platform/applications/{crm}", json={"appUrl": "http://localhost:4302"}, headers=ana)
    r = client.post("/platform/applications/adopt-address", json={"platformUrl": "https://platform-bishnoi.local"}, headers=ana)
    assert r.status_code == 200, r.text
    got = addresses(client, ana)
    assert got["platform"] == "https://platform-bishnoi.local"
    assert got["crm"] == "https://crm-bishnoi.local"
    assert got["exec"] == "https://admin-bishnoi.local"

    # A new domain later: the apps that followed the old one follow again.
    client.post("/platform/applications/adopt-address", json={"platformUrl": "https://platform.bishnoi-one.cloud-ip.cc"}, headers=ana)
    assert addresses(client, ana)["crm"] == "https://crm.bishnoi-one.cloud-ip.cc"


def test_a_hand_set_address_and_odd_visits_are_left_alone(client, ana, ben):
    inv = app_id(client, ana, "inventory")
    client.patch(f"/platform/applications/{inv}", json={"appUrl": "https://stock.example.com"}, headers=ana)
    client.post("/platform/applications/adopt-address", json={"platformUrl": "https://platform-bishnoi.local"}, headers=ana)
    assert addresses(client, ana)["inventory"] == "https://stock.example.com"
    # Not a name for the platform (an IP, localhost): nothing moves.
    before = addresses(client, ana)
    for url in ("http://192.168.1.160:4305", "http://localhost:4305", "https://example.com"):
        assert client.post("/platform/applications/adopt-address", json={"platformUrl": url}, headers=ana).json() == {"changed": []}
    assert addresses(client, ana) == before
    # Only administrators.
    assert client.post("/platform/applications/adopt-address", json={"platformUrl": "https://platform.evil.example"}, headers=ben).status_code == 403
