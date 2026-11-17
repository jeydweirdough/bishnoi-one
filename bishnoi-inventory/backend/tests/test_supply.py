"""Order-on-demand, consignment and documents with products (feature plan steps 15b, 15d, 15e; dropshipping, 15c, removed 2026-11-17)."""

from tests.conftest import receive, sold
from tests.test_sales import outbox


def a_sales_order(ana, world, quantity, **extra):
    made = ana.post("/inventory/sales-orders", {"customerName": "PGH", "customerAddress": "Taft Ave, Manila", "lines": [{"productId": world["gloves"], "quantity": quantity}], **extra})
    ana.post(f"/inventory/sales-orders/{made['id']}/submit")
    return made


def test_an_order_without_the_stock_raises_a_draft_purchase_order(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 3}])
    made = a_sales_order(ana, world, 10)
    approved = ana.post(f"/inventory/sales-orders/{made['id']}/approve")
    assert approved["delivery"] is not None
    pos = approved["purchaseOrders"]
    assert len(pos) == 1 and pos[0]["status"] == "draft" and pos[0]["supplier"] == "ABC Medical Supply"
    po = ana.get(f"/inventory/purchase-orders/{pos[0]['id']}")
    assert po["lines"][0]["quantity"] == 7 and po["salesOrder"]["number"] == made["number"]
    # Enough stock: nothing raised.
    other = a_sales_order(ana, world, 2)
    assert ana.post(f"/inventory/sales-orders/{other['id']}/approve")["purchaseOrders"] == []


def test_consignment_stock_is_the_vendors_until_it_sells(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 10}], supplierId=world["supplier"], consignment=True)
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 5}])
    value = ana.get("/inventory/reports/valuation")["rows"][0]
    assert value["onHand"] == 5  # ours only
    o = sold(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 12}])
    ana.post(f"/inventory/orders/{o['id']}/confirm")
    ana.post(f"/inventory/orders/{o['id']}/issue", {})
    rows = ana.get("/inventory/reports/consignment")["rows"]
    gone = sum(r["sold"] for r in rows)
    left = sum(r["left"] for r in rows)
    assert gone + left == 10 and rows[0]["vendor"] == "ABC Medical Supply" and rows[0]["toPay"] == rows[0]["sold"] * rows[0]["unitCost"]


def test_documents_go_with_every_sale(ana, world):
    r = ana.c.post(f"/inventory/products/{world['gloves']}/documents", headers=ana.h,
                   files={"file": ("coa.pdf", b"%PDF-1.4 test", "application/pdf")}, data={"name": "Certificate of analysis"})
    assert r.status_code == 201, r.text
    doc = r.json()[0]
    assert doc["name"] == "Certificate of analysis" and doc["sendWithSales"]
    assert ana.c.post(f"/inventory/products/{world['gloves']}/documents", headers=ana.h, files={"file": ("x.exe", b"MZ", "application/x-msdownload")}).status_code == 415
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 5}])
    o = sold(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 1}])
    assert [d["name"] for d in ana.get(f"/inventory/orders/{o['id']}/documents")] == ["Certificate of analysis"]
    assert ana.c.get(doc["href"], headers=ana.h).content.startswith(b"%PDF")
    ana.patch(f"/inventory/products/{world['gloves']}/documents/{doc['id']}", {"sendWithSales": False})
    assert ana.get(f"/inventory/orders/{o['id']}/documents") == []


def test_consignment_is_settled_once_and_sent_to_finance(app, ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 10}], supplierId=world["supplier"], consignment=True)
    product = ana.get(f"/inventory/products/{world['gloves']}")
    assert product["consigned"] == 10 and product["value"] == 0  # theirs, not ours
    stock = ana.get("/inventory/stock")["items"]
    assert sum(r["value"] for r in stock) == 0
    o = sold(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 4}])
    ana.post(f"/inventory/orders/{o['id']}/confirm")
    ana.post(f"/inventory/orders/{o['id']}/issue", {})
    vendor = ana.get("/inventory/consignment")["vendors"][0]
    assert vendor["toPay"] == 4 * 18500 and vendor["lines"][0]["quantity"] == 4
    s = ana.post(f"/inventory/consignment/{world['supplier']}/settle")
    assert s["number"].startswith("CS-") and s["total"] == 74000
    billed = outbox(app, "consignment.billed")[-1]
    assert billed["number"] == s["number"] and billed["supplier"]["name"] == "ABC Medical Supply" and billed["totalCentavos"] == 74000
    # Settled: nothing more to pay until more sells.
    assert ana.get("/inventory/consignment")["vendors"][0]["toPay"] == 0
    assert ana.c.post(f"/inventory/consignment/{world['supplier']}/settle", headers=ana.h).status_code == 409


def test_a_sales_documents_are_emailed_to_the_customer(ana, world, monkeypatch):
    from app import mail

    sent = []
    monkeypatch.setattr(mail, "send", lambda settings, company, to, subject, text, attachments: sent.append((to, subject, [a[0] for a in attachments])))
    ana.c.post(f"/inventory/products/{world['gloves']}/documents", headers=ana.h, files={"file": ("coa.pdf", b"%PDF-1.4 x", "application/pdf")}, data={"name": "COA"})
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 2}])
    o = sold(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 1}])
    assert ana.c.post(f"/inventory/orders/{o['id']}/documents/send", headers=ana.h, json={"to": ["not-an-email"]}).status_code == 422
    r = ana.post(f"/inventory/orders/{o['id']}/documents/send", {"to": ["Buyer@PGH.gov.ph"], "message": "Good day."})
    assert r == {"sent": 1, "to": ["buyer@pgh.gov.ph"]}
    assert sent == [(["buyer@pgh.gov.ph"], f"Documents for {o['number']}", ["coa.pdf"])]


def test_without_an_email_service_it_says_how_to_set_one_up(ana, world):
    ana.c.post(f"/inventory/products/{world['gloves']}/documents", headers=ana.h, files={"file": ("coa.pdf", b"%PDF-1.4 x", "application/pdf")}, data={"name": "COA"})
    o = sold(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 1}])
    r = ana.c.post(f"/inventory/orders/{o['id']}/documents/send", headers=ana.h, json={"to": ["buyer@pgh.gov.ph"]})
    assert r.status_code == 409 and "connected" in r.json()["detail"]
