"""The invoice is the order's source of truth (owner's Step 4D): once Finance issues the invoice for a sales order's
delivery, the order shows the invoice's amounts and state, nothing on it can drift from the invoice, a void clears
it until the reissue, and the reports count the invoice's figures."""

from modules.inventory.models import SalesOrder
from modules.inventory.sales import invoice_out, status_label
from modules.inventory.tests.test_platform_roles import database, note
from modules.inventory.tests.test_platform_sign_in import linked  # noqa: F401 (fixture)
from modules.inventory.tests.test_shipping import a_delivery

N = 0


def hear(client, kind: str, data: dict) -> None:
    global N
    N += 1
    event = {"id": f"ev-truth-{N:04d}", "kind": kind, "source": "finance", "occurredAt": "2026-11-18T00:00:00+00:00", "data": data}
    r = client.post("/platform/events", json={"pass": note("event", event=event)})
    assert r.status_code == 204, r.text


LINES = [{"ref": "GLV-M", "description": "Gloves M", "quantity": 3, "unitPriceCentavos": 32000, "discountCentavos": 6000,
          "taxCentavos": 9643, "totalCentavos": 90000}]


def delivered(ana, world) -> dict:
    d = a_delivery(ana, world, quantity=3)
    ana.post(f"/inventory/orders/{d['id']}/confirm")
    ana.post(f"/inventory/orders/{d['id']}/issue", {})
    return d


def issued(client, d: dict, inv="inv-1", number="SI-000101", total=90000) -> None:
    hear(client, "invoice.issued", {"id": inv, "number": number, "totalCentavos": total, "taxCentavos": 9643, "grossCentavos": 96000,
                                    "discountCentavos": 6000, "lines": LINES, "deliveryId": d["id"], "salesOrderId": d["salesOrder"]["id"]})


def test_an_invoiced_order_shows_the_invoices_amounts_and_state(app, client, ana, world, linked):  # noqa: F811
    d = delivered(ana, world)
    so = d["salesOrder"]["id"]
    before = ana.get(f"/inventory/sales-orders/{so}")
    assert before["totalCentavos"] == 96000 and before["amountsFrom"] == "order" and before["statusLabel"] == "Delivered"
    issued(client, d)
    o = ana.get(f"/inventory/sales-orders/{so}")
    assert o["statusLabel"] == "Invoiced" and o["amountsFrom"] == "invoice" and o["invoiceState"] == "issued"
    assert (o["grossCentavos"], o["discountCentavos"], o["taxCentavos"], o["totalCentavos"]) == (96000, 6000, 9643, 90000)
    assert o["ordered"]["totalCentavos"] == 96000  # the order's own amounts are still there, as ordered
    assert o["invoice"]["lines"] == LINES
    listed = next(x for x in ana.get("/inventory/sales-orders") if x["id"] == so)
    assert listed["totalCentavos"] == 90000 and listed["statusLabel"] == "Invoiced"
    hear(client, "invoice.paid", {"id": "inv-1", "number": "SI-000101", "salesOrderId": so, "paidAt": "2026-11-19T02:00:00+00:00"})
    assert ana.get(f"/inventory/sales-orders/{so}")["statusLabel"] == "Paid"


def test_the_quote_hears_the_invoices_figures(app, client, ana, world, linked):  # noqa: F811
    d = delivered(ana, world)
    issued(client, d)
    with database(app)() as db:
        order = db.get(SalesOrder, d["salesOrder"]["id"])
        out, label = invoice_out(order), status_label(order)
    assert label == "Invoiced"
    assert out["number"] == "SI-000101" and out["state"] == "issued" and out["totalCentavos"] == 90000 and out["taxCentavos"] == 9643


def test_an_invoiced_order_cant_drift_from_its_invoice(app, client, ana, world, linked):  # noqa: F811
    d = delivered(ana, world)
    so = d["salesOrder"]["id"]
    issued(client, d)
    body = {"customerName": "Someone else", "lines": [{"productId": world["gloves"], "quantity": 1}]}
    r = ana.c.put(f"/inventory/sales-orders/{so}", headers=ana.h, json=body)
    assert r.status_code == 409 and "invoiced (SI-000101)" in r.json()["detail"] and "void and reissue" in r.json()["detail"]
    r = ana.c.post(f"/inventory/sales-orders/{so}/cancel", headers=ana.h)
    assert r.status_code == 409 and "can't be cancelled" in r.json()["detail"]
    # The fee charged to the customer is an invoice line: it doesn't change once invoiced.
    r = ana.c.put(f"/inventory/orders/{d['id']}/shipping", headers=ana.h, json={"method": "own", "fee": 5000, "feeCharged": True})
    assert r.status_code == 409 and "SI-000101" in r.json()["detail"]
    # How it goes still can (that isn't on the invoice).
    assert ana.c.put(f"/inventory/orders/{d['id']}/shipping", headers=ana.h, json={"method": "pickup"}).status_code == 200
    # Nor do the order or its delivery go to the recycle bin.
    for kind, rid in (("sales-orders", so), ("deliveries", d["id"])):
        r = client.post(f"/data-cleanup/kinds/{kind}/delete", json={"ids": [rid], "confirmPosted": True}, headers=ana.h)
        assert r.status_code == 409 and "SI-000101" in r.text, r.text


def test_a_voided_invoice_clears_the_order_until_its_reissue_replaces_it(app, client, ana, world, linked):  # noqa: F811
    d = delivered(ana, world)
    so = d["salesOrder"]["id"]
    issued(client, d)
    # Finance's void names only the invoice: the order is found by it.
    hear(client, "invoice.voided", {"id": "inv-1", "number": "SI-000101", "totalCentavos": 90000, "reason": "Wrong discount"})
    o = ana.get(f"/inventory/sales-orders/{so}")
    assert o["statusLabel"] == "Invoice voided — waiting for reissue" and o["amountsFrom"] == "order" and o["totalCentavos"] == 96000
    assert o["invoice"]["voidReason"] == "Wrong discount" and o["invoice"]["totalCentavos"] is None
    r = ana.c.put(f"/inventory/sales-orders/{so}", headers=ana.h, json={"customerName": "X", "lines": [{"productId": world["gloves"], "quantity": 1}]})
    assert r.status_code == 409 and "voided" in r.json()["detail"]
    # The reissue carries no sales order, only what it replaces.
    hear(client, "invoice.issued", {"id": "inv-2", "number": "SI-000102", "totalCentavos": 96000, "taxCentavos": 10286, "grossCentavos": 96000,
                                    "discountCentavos": 0, "lines": [], "deliveryId": None, "salesOrderId": None, "replacesId": "inv-1"})
    o = ana.get(f"/inventory/sales-orders/{so}")
    assert o["invoice"]["number"] == "SI-000102" and o["statusLabel"] == "Invoiced" and o["taxCentavos"] == 10286
    # Its payment, which names no sales order either, still reaches the order.
    hear(client, "invoice.paid", {"id": "inv-2", "number": "SI-000102", "salesOrderId": None, "paidAt": "2026-11-20T02:00:00+00:00"})
    assert ana.get(f"/inventory/sales-orders/{so}")["statusLabel"] == "Paid"


def test_a_reissue_without_a_void_event_still_replaces_the_invoice(app, client, ana, world, linked):  # noqa: F811
    """Finance's Cancel and reissue voids without sending invoice.voided: the replacement still takes the order."""
    d = delivered(ana, world)
    issued(client, d)
    hear(client, "invoice.issued", {"id": "inv-9", "number": "SI-000109", "totalCentavos": 95000, "replacesId": "inv-1"})
    o = ana.get(f"/inventory/sales-orders/{d['salesOrder']['id']}")
    assert o["invoice"]["number"] == "SI-000109" and o["totalCentavos"] == 95000


def test_reports_count_the_invoices_figures_once_invoiced(app, client, ana, world, linked):  # noqa: F811
    d = delivered(ana, world)
    other = delivered(ana, world)  # not invoiced: its own amount
    issued(client, d)
    rows = {r["name"]: r for r in ana.get("/inventory/reports/sales-orders-by-status")["rows"]}
    assert rows["Invoiced"]["value"] == 90000 and rows["Delivered"]["value"] == 96000
    cash = {r["order"]: r for r in ana.get("/inventory/reports/order-to-cash")["rows"]}
    assert cash[d["salesOrder"]["number"]]["value"] == 90000 and cash[d["salesOrder"]["number"]]["stage"] == "Invoiced"
    assert cash[other["salesOrder"]["number"]]["value"] == 96000
    by_person = ana.get("/inventory/reports/sales-orders-by-salesperson")
    assert sum(r["value"] for r in by_person["rows"]) == 186000
    assert "invoice's total once invoiced" in str(by_person)
