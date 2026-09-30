"""The sidebar's red counts: what isn't set up yet."""

from datetime import UTC, datetime, timedelta

from .test_executive import app, auth_header, client  # noqa: F401 (fixtures)

LATER = (datetime.now(UTC) + timedelta(days=80)).date().isoformat()


def lease(client, headers, name, **extra) -> dict:  # noqa: F811 (not the fixture)
    body = {"name": name, "propertyType": "office", "address": "Ayala Ave, Makati City", "lessorName": "Ayala Land Offices", "leaseEnd": LATER, "status": "active", **extra}
    r = client.post("/admin/properties", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def document(client, headers, title, **extra) -> dict:  # noqa: F811 (not the fixture)
    body = {"title": title, "category": "insurance", "counterparty": "Malayan Insurance", "autoRenews": False, "status": "active", **extra}
    r = client.post("/admin/documents", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_what_is_left_out_is_counted(client, auth_header):  # noqa: F811 (fixtures)
    assert client.get("/admin/unset", headers=auth_header).json() == {}
    lease(client, auth_header, "Tower One", monthlyRent=350000.0)
    no_rent = lease(client, auth_header, "Warehouse B")
    lease(client, auth_header, "Old branch", status="terminated")  # ended: nothing to fix
    document(client, auth_header, "Fire insurance", expirationDate=LATER)
    document(client, auth_header, "Service contract", autoRenews=True)  # renews by itself
    no_expiry = document(client, auth_header, "Liability insurance")
    assert client.get("/admin/unset", headers=auth_header).json() == {"propertyRent": 1, "documentExpiry": 1}
    assert [p["id"] for p in client.get("/admin/properties?missing=true", headers=auth_header).json()] == [no_rent["id"]]
    assert [d["id"] for d in client.get("/admin/documents?missing=true", headers=auth_header).json()] == [no_expiry["id"]]
