"""Automatic invoicing (feature plan step 13, 2026-10-29): a customer's delivery leaving the warehouse
(the event delivery.done, from the Sales app's sales order) becomes its invoice here, with nobody retyping it.

- One invoice per delivery (nbfi_invoices.delivery_id is unique; an event heard twice makes nothing new).
- The lines are the sale's: each product at the price and discount it was sold at, with its VAT category
  from the CRM; free goods as their own lines at no charge; a shipping fee charged to the customer as a
  line of its own. The customer, salesperson, division and team as the order had them.
- Issued at once (numbered from the BIR series, tax from the engine, posted, cost of goods sold booked)
  when the company chose so (nbfi_ledger_settings.auto_invoice = "issue", the default); otherwise, or
  when it can't be (no numbers left, the tax registration incomplete), it waits as a draft with why
  (Invoice.attention), for Finance to fix and issue.
- The delivery → invoice link goes to the document chain (step 9); invoice.issued tells the Sales app
  and the CRM.

A delivery that isn't a sale (an issue to a department or project) or has no sales order isn't invoiced.
"""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import business_events
from app.audit import audit
from app.ledger import settings as posting_settings
from app.models import Invoice

ACTOR = "Bishnoi One"


def lines_of(sale: dict, shipping: dict | None) -> list[dict]:
    """The invoice lines for what was sold, in the tax engine's shape."""
    lines = []
    for line in sale.get("lines") or []:
        sku, name = str(line.get("sku") or "")[:60] or None, str(line.get("name") or line.get("sku") or "Item")[:200]
        category = str(line.get("vatCategory") or "standard")[:20]
        quantity = int(line.get("quantity") or 0)
        if quantity > 0:
            lines.append({"ref": sku, "description": name, "quantity": quantity, "unitPriceCentavos": int(line.get("unitPriceCentavos") or 0),
                          "discountCentavos": int(line.get("discountCentavos") or 0), "category": category, "reliefEligible": False})
        free = int(line.get("freeQuantity") or 0)
        if free > 0:
            lines.append({"ref": sku, "description": f"{name} (free)"[:200], "quantity": free, "unitPriceCentavos": 0,
                          "discountCentavos": 0, "category": category, "reliefEligible": False})
    if shipping and shipping.get("feeCharged") and int(shipping.get("fee") or 0) > 0:
        how = " · ".join(x for x in (shipping.get("courier"), shipping.get("trackingNumber")) if x)
        lines.append({"ref": None, "description": f"Shipping fee{f' ({how})' if how else ''}"[:200], "quantity": 1,
                      "unitPriceCentavos": int(shipping["fee"]), "discountCentavos": 0, "category": "standard", "reliefEligible": False})
    return lines


def from_delivery(db: Session, data: dict, slug: str | None) -> Invoice | None:
    """The invoice for a delivery that left the warehouse (delivery.done); None when it isn't one to invoice."""
    from app.business_events import _state
    from app.routers.funds import today
    from app.routers.invoices import issue_now

    sale = data.get("salesOrder") or None
    delivery_id = str(data.get("orderId") or "")[:36]
    if not sale or not delivery_id:
        return None
    found = db.scalar(select(Invoice).where(Invoice.delivery_id == delivery_id))
    if found is not None:
        return found
    lines = lines_of(sale, data.get("shipping"))
    if not lines:
        return None
    settings = _state.get("settings")
    customer = sale.get("customer") or {}
    person, division, team = sale.get("salesperson") or {}, sale.get("division") or {}, sale.get("team") or {}
    quote = sale.get("quote") or {}
    inv = Invoice(
        created_by=f"{ACTOR} (from {data.get('number')})", customer_id=customer.get("id"),
        customer_name=str(customer.get("name") or data.get("recipient") or "Customer")[:200],
        customer_tin=(str(customer["tin"])[:20] if customer.get("tin") else None),
        customer_address=(str(customer["address"])[:300] if customer.get("address") else None),
        salesperson_id=person.get("id"), salesperson_name=person.get("name"),
        division_id=division.get("id"), division_name=division.get("name"), team_id=team.get("id"), team_name=team.get("name"),
        invoice_date=today(settings) if settings is not None else datetime.now(UTC).date(),
        reference=str(sale.get("number") or "")[:80] or None,
        notes=f"Delivered on {data.get('number')}" + (f", from quote {quote.get('number')}" if quote.get("number") else ""),
        prices_include_tax=sale.get("pricesIncludeTax"), lines=lines,
        delivery_id=delivery_id, delivery_number=str(data.get("number") or "")[:30] or None,
        sales_order_id=str(sale.get("id") or "")[:36] or None, sales_order_number=str(sale.get("number") or "")[:30] or None,
    )
    db.add(inv)
    db.flush()
    audit(db, ACTOR, "invoice.drafted", target=inv.customer_name, target_type="invoice", target_id=inv.id, fields=[f"from {inv.delivery_number}"])
    if posting_settings(db).auto_invoice == "issue" and settings is not None:
        try:
            with db.begin_nested():
                issue_now(db, settings, inv, ACTOR, ACTOR)
        except HTTPException as e:
            inv.attention = (e.detail if isinstance(e.detail, str) else "It couldn't be issued by itself: check it and issue it.")[:300]
    elif settings is not None:
        inv.attention = "Made from the delivery as a draft (Invoices are set to wait for Finance): check it and issue it."
    business_events.link(db, slug, business_events.ref("order", delivery_id, inv.delivery_number, app="inventory"), business_events.ref("invoice", inv.id, inv.number))
    return inv
