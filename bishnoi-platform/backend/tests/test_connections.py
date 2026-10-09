"""Connections: the platform tells each application what it's linked to, so
addresses and keys between applications are set in one place."""

from tests.conftest import app_id


def connect(client, admin, key: str) -> str:
    r = client.post(f"/platform/applications/{app_id(client, admin, key)}/connect-key", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()["key"]


def asks(client, connect_key: str):
    return client.get("/connect/links", headers={"X-Bishnoi-App-Key": connect_key})


def test_applications_learn_their_links_from_the_platform(client, ana, ben):
    crm_key, inventory_key = connect(client, ana, "crm"), connect(client, ana, "inventory")
    assert crm_key.startswith("bpk.crm.")
    assert asks(client, crm_key).json() == {"app": "crm", "appUrl": "http://localhost:4302", "uses": {}, "usedBy": {}, "askAgainIn": 300}
    assert asks(client, "bpk.crm.made-up").status_code == 401

    # Only links the applications understand are offered, and made.
    seen = client.get("/platform/connections", headers=ben).json()  # anyone on the platform can look
    assert {(o["from"]["key"], o["to"]["key"]) for o in seen["offered"]} >= {("crm", "inventory"), ("crm", "finance"), ("finance", "crm")}
    assert client.post("/platform/links", json={"fromAppId": app_id(client, ana, "inventory"), "toAppId": app_id(client, ana, "crm")}, headers=ana).status_code == 422
    assert client.post("/platform/links", json={"fromAppId": app_id(client, ana, "crm"), "toAppId": app_id(client, ana, "inventory")}, headers=ben).status_code == 403  # only an admin changes them

    made = client.post("/platform/links", json={"fromAppId": app_id(client, ana, "crm"), "toAppId": app_id(client, ana, "inventory")}, headers=ana)
    assert made.status_code == 201, made.text
    link = made.json()["link"]
    assert link["state"] == "waiting"  # neither has asked since

    crm = asks(client, crm_key).json()
    inventory = asks(client, inventory_key).json()
    key = crm["uses"]["inventory"]["key"]
    assert crm["uses"]["inventory"] == {"apiUrl": "http://127.0.0.1:8304", "appUrl": "http://localhost:4304", "key": key}
    assert inventory["usedBy"] == {"crm": key} and inventory["uses"] == {}
    listed = {(l["from"]["key"], l["to"]["key"]): l for l in client.get("/platform/connections", headers=ana).json()["links"]}
    assert listed[("crm", "inventory")]["isOn"] and listed[("crm", "inventory")]["state"] in ("working", "problem")  # problem: Inventory's API isn't up in tests

    # Off: both lose it. A new key: both get the new one, the old one stops.
    client.patch(f"/platform/links/{link['id']}", json={"isOn": False}, headers=ana)
    assert asks(client, crm_key).json()["uses"] == {} and asks(client, inventory_key).json()["usedBy"] == {}
    client.patch(f"/platform/links/{link['id']}", json={"isOn": True}, headers=ana)
    client.post(f"/platform/links/{link['id']}/new-key", headers=ana)
    fresh = asks(client, crm_key).json()["uses"]["inventory"]["key"]
    assert fresh != key and asks(client, inventory_key).json()["usedBy"] == {"crm": fresh}

    # A replaced connect key stops working; disconnecting stops the app's answers.
    new_crm_key = connect(client, ana, "crm")
    assert asks(client, crm_key).status_code == 401 and asks(client, new_crm_key).status_code == 200
    assert client.delete(f"/platform/applications/{app_id(client, ana, 'crm')}/connect-key", headers=ana).status_code == 204
    assert asks(client, new_crm_key).status_code == 401


def test_link_keys_are_kept_encrypted(app, client, ana):
    from sqlalchemy import select

    from app.models import AppLink

    connect(client, ana, "crm")
    client.post("/platform/links", json={"fromAppId": app_id(client, ana, "crm"), "toAppId": app_id(client, ana, "finance")}, headers=ana)
    with app.state.sessions() as db:
        sealed = db.scalar(select(AppLink)).secret
    assert sealed.startswith("gAAAA")  # a Fernet token, not the key itself
