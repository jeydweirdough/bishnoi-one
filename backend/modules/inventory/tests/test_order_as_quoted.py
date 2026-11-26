"""A sales order carries what its quote carried, and one made directly with the quote form is priced the same way
(2026-11-23, owner: the quotation is the sales order's basis; a direct sale needn't make a quote)."""

import base64

from modules.inventory.tests.conftest import INTEGRATION_KEY
from modules.inventory.tests.test_platform_roles import note
from modules.inventory.tests.test_platform_sign_in import linked  # noqa: F401 (fixture)
from modules.inventory.tests.test_sales import outbox

KEY = {"X-Bishnoi-Key": INTEGRATION_KEY}


def priced(world, **more) -> dict:
    """The CRM's order payload (modules/crm/orders.py), as a quote or the quote form priced it."""
    return {
        "customer": {"kind": "company", "id": "c-1", "name": "Agape Clinic Parañaque", "address": "Parañaque", "tin": "123-456-789-000",
                     "email": "orders@agape.example", "phone": "0917 000 0000"},
        "salesperson": {"id": "u-1", "name": "Jasper Catubig"}, "team": {"id": "t-1", "name": "CLIDP"}, "division": {"id": "d-1", "name": "Rx"},
        "raisedBy": {"name": "Jasper Catubig", "email": "jasper@example.com"}, "payer": {"kind": "customer"}, "currency": "PHP",
        "pricing": {"priceType": "SRP", "priceTypeName": "SRP", "rx": True, "terms": "30 days", "approvalReasons": ["discount", "rx"],
                    "warnings": ["CLIDP: Loratadine is under a CLIDP for this customer."]},
        "lines": [{"inventoryId": world["gloves"], "code": "GLV-M", "name": "Gloves M", "quantity": 4, "freeQuantity": 4, "unitPriceCentavos": 30000,
                   "discountCentavos": 15000, "promoName": "Buy 1, get 1 free", "promoDiscountCentavos": 0, "extraDiscountCentavos": 15000,
                   "discountKind": "percent", "discountValue": 1250, "totalCentavos": 105000, "vatCategory": "standard"}],
        "tax": {"pricesIncludeTax": True, "totalDueCentavos": 105000}, **more,
    }


def test_a_direct_order_keeps_the_price_type_promos_discounts_and_letter(app, client, ana, world):
    letter = {"number": "GL-77", "issuedOn": "2026-11-20", "amountCentavos": 105000, "fileName": "gl.pdf", "fileType": "application/pdf",
              "fileBase64": base64.b64encode(b"%PDF-1.4 letter").decode()}
    body = priced(world, payer={"kind": "guarantee_letter", "issuer": "PCSO", "letterNumber": "GL-77", "amountCentavos": 105000},
                  letter=letter, scheduledOn="2026-11-25")
    r = client.post("/integration/sales-orders", headers=KEY, json=body)
    assert r.status_code == 201, r.text
    made = r.json()
    o = ana.get(f"/inventory/sales-orders/{made['id']}")
    assert o["status"] == "pending" and o["source"] == "direct" and o["quote"] is None
    assert o["priceType"] == {"code": "SRP", "name": "SRP"} and o["rx"] is True and o["terms"] == "30 days"
    assert o["approvalReasons"] == ["discount", "rx"] and o["warnings"][0].startswith("CLIDP")
    assert o["customer"]["tin"] == "123-456-789-000" and o["customer"]["email"] == "orders@agape.example"
    line = o["lines"][0]
    assert line["promoName"] == "Buy 1, get 1 free" and line["freeQuantity"] == 4
    assert (line["discount"], line["extraDiscount"], line["discountKind"], line["discountValue"]) == (15000, 15000, "percent", 1250)
    assert o["tax"]["totalDueCentavos"] == 105000 and o["scheduledOn"] == "2026-11-25"
    assert o["letter"]["number"] == "GL-77" and o["letter"]["hasFile"] is True
    got = ana.c.get(f"/inventory/sales-orders/{made['id']}/letter", headers=ana.h)
    assert got.status_code == 200 and got.content == b"%PDF-1.4 letter"
    # The approvers read why it needs approval, and that no pharmacist checked the prescription.
    slip = outbox(app, "approval.requested")[-1]
    assert slip["summary"]["approvalReasons"] == ["discount", "rx"] and slip["summary"]["priceType"] == "SRP"
    assert any("no Pharmacy check" in a["label"] for a in slip["attachments"])
    # Only another Bishnoi One app makes one.
    assert client.post("/integration/sales-orders", json=body).status_code == 401


def test_a_direct_order_with_nothing_inventory_has_is_refused(client, world):
    body = priced(world)
    body["lines"][0]["inventoryId"], body["lines"][0]["code"] = None, "NOPE"
    r = client.post("/integration/sales-orders", headers=KEY, json=body)
    assert r.status_code == 409 and "Inventory" in r.json()["detail"]


def test_an_order_from_a_quote_keeps_its_pricing_too(app, client, ana, world, linked):  # noqa: F811
    data = priced(world, quote={"id": "q-9", "number": "Q-2026-0009", "notes": "Deliver before noon", "priceType": "SRP", "rx": True})
    event = {"id": "ev-quote-0009", "kind": "quote.ordered", "source": "crm", "data": data, "occurredAt": "2026-11-23T00:00:00+00:00"}
    assert client.post("/platform/events", json={"pass": note("event", event=event)}).status_code == 204
    o = ana.get(f"/inventory/sales-orders/{ana.get('/inventory/sales-orders')[0]['id']}")
    assert o["source"] == "quote" and o["quote"]["number"] == "Q-2026-0009" and o["notes"] == "Deliver before noon"
    assert o["priceType"]["name"] == "SRP" and o["lines"][0]["promoName"] == "Buy 1, get 1 free" and o["promoDiscountCentavos"] == 0
