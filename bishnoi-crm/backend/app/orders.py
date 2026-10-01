"""Raising an order in Nabhi Order from a ready quote.

Nabhi Order is its own application; the CRM only sends it the quote. "Raise
order" on a quote POSTs the payload below to

    {ORDERS_API_URL}/orders
    X-Nabhi-Key: {ORDERS_API_KEY}
    Idempotency-Key: {the quote's id}
    Content-Type: application/json

and expects 200 or 201 with at least {"id": "...", "number": "..."}, plus
optionally "url" (the order's page, for the "Open order" link) and "status".
The same quote sent twice carries the same Idempotency-Key, so Nabhi Order can
answer with the order it already made instead of a second one.

The payload (amounts in centavos, dates as YYYY-MM-DD):

    {
      "source": "nabhi-crm",
      "quote": {"id", "number", "createdAt", "validUntil", "terms", "notes", "priceType", "rx"},
      "customer": {"kind": "company" | "contact", "id", "name", "address", "email", "phone"},
      "team": {"id", "name"} | null,
      "salesperson": {"id", "name", "email"},
      "raisedBy": {"id", "name", "email"},
      "payer": {"kind": "customer"} | {"kind": "guarantee_letter", "issuer", "letterNumber", "amountCentavos"},
      "lines": [{"productId", "inventoryId", "code", "name", "unit", "quantity", "freeQuantity",
                 "unitPriceCentavos", "discountCentavos", "totalCentavos", "bundle"}],
      "totals": {"grossCentavos", "promoDiscountCentavos", "discountCentavos", "totalCentavos"},
      "tax": {...Finance's tax summary...} | null,
      "currency": "PHP"
    }
"""

import json
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Company, Contact, Product, Quote, Team, User

TIMEOUT = 15  # seconds


class OrdersUnavailable(Exception):
    """Nabhi Order didn't answer, or refused: the message says which, for people."""


def text(record: Any, *names: str) -> str | None:
    for name in names:
        value = getattr(record, name, None)
        if value:
            return str(value)
    return None


def address_of(company: Company | None) -> str | None:
    if company is None:
        return None
    return ", ".join(p for p in (company.address, company.city, company.country) if p) or None


def person(user: User | None) -> dict | None:
    return {"id": user.id, "name": user.full_name, "email": user.email} if user else None


def payload(db: Session, quote: Quote, me: User, settings: Settings) -> dict:
    """What Nabhi Order receives for a quote. See the module's docstring."""
    contact = db.get(Contact, quote.contact_id) if quote.contact_id else None
    company = db.get(Company, quote.company_id) if quote.company_id else (contact.company if contact else None)
    customer = contact or company
    team = db.get(Team, quote.team_id) if quote.team_id else None
    owner = db.get(User, quote.owner_id) if quote.owner_id else None
    letter = quote.letter or {}
    lines = []
    for line in quote.lines:
        product = db.get(Product, line.get("productId")) if line.get("productId") else None
        lines.append({
            "productId": line.get("productId"),
            "inventoryId": product.inventory_id if product else None,
            "code": line.get("productCode"),
            "name": line.get("productName"),
            "unit": line.get("unit"),
            "quantity": line.get("quantity", 0),
            "freeQuantity": line.get("freeQuantity", 0),
            "unitPriceCentavos": line.get("unitPriceCentavos", 0),
            "discountCentavos": (line.get("promoDiscountCentavos") or 0) + (line.get("discountCentavos") or 0),
            "totalCentavos": line.get("totalCentavos", 0),
            "bundle": line.get("bundleName"),
        })
    return {
        "source": "nabhi-crm",
        "quote": {
            "id": quote.id,
            "number": quote.number,
            "createdAt": quote.created_at.date().isoformat() if quote.created_at else None,
            "validUntil": quote.valid_until,
            "terms": quote.terms,
            "notes": quote.notes,
            "priceType": quote.price_type_name,
            "rx": quote.rx,
        },
        "customer": {
            "kind": "contact" if contact else "company",
            "id": customer.id if customer else None,
            "name": quote.customer_name,
            "address": address_of(company),
            "email": text(customer, "email"),
            "phone": text(customer, "phone", "mobile"),
        },
        "team": {"id": team.id, "name": team.name} if team else None,
        "salesperson": person(owner),
        "raisedBy": person(me),
        "payer": (
            {"kind": "guarantee_letter", "issuer": quote.payer_name, "letterNumber": letter.get("number"), "amountCentavos": letter.get("amountCentavos")}
            if quote.payer != "self"
            else {"kind": "customer"}
        ),
        "lines": lines,
        "totals": {
            "grossCentavos": quote.gross_centavos,
            "promoDiscountCentavos": quote.promo_discount_centavos,
            "discountCentavos": quote.discount_centavos,
            "totalCentavos": quote.total_centavos,
        },
        "tax": quote.tax,
        "currency": settings.org_currency,
    }


def send(settings: Settings, quote_id: str, body: dict) -> dict:
    """POSTs the order to Nabhi Order and returns what it made."""
    request = urllib.request.Request(
        f"{settings.orders_api_url.rstrip('/')}/orders",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "X-Nabhi-Key": settings.orders_api_key.get_secret_value(),
            "Idempotency-Key": quote_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 (the address is ours, from settings)
            made = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise OrdersUnavailable("Nabhi Order refused the CRM's key: check ORDERS_API_KEY.") from e
        detail = ""
        try:
            detail = json.loads(e.read() or b"{}").get("detail") or ""
        except (ValueError, AttributeError):
            pass
        message = f"Nabhi Order didn't take the order ({e.code})."
        raise OrdersUnavailable(f"{message} {detail}".strip() if isinstance(detail, str) else message) from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise OrdersUnavailable("Nabhi Order can't be reached right now. Try again in a moment.") from e
    if not isinstance(made, dict) or not made.get("id") or not made.get("number"):
        raise OrdersUnavailable("Nabhi Order answered without an order number.")
    return made
