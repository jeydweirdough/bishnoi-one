"""Raising an order in Bishnoi One Order from a ready quote.

Bishnoi One Order is its own application; the CRM only sends it the quote. "Raise
order" on a quote POSTs the payload below to

    {ORDERS_API_URL}/orders
    X-Bishnoi-Key: {ORDERS_API_KEY}
    Idempotency-Key: {the quote's id}
    Content-Type: application/json

and expects 200 or 201 with at least {"id": "...", "number": "..."}, plus
optionally "url" (the order's page, for the "Open order" link) and "status".
The same quote sent twice carries the same Idempotency-Key, so Bishnoi One Order can
answer with the order it already made instead of a second one.

The payload (amounts in centavos, dates as YYYY-MM-DD):

    {
      "source": "bishnoi-crm",
      "quote": {"id", "number", "createdAt", "validUntil", "terms", "notes", "priceType", "rx"},
      "customer": {"kind": "company" | "contact", "id", "name", "address", "email", "phone"},
      "team": {"id", "name"} | null,
      "salesperson": {"id", "name", "email"},
      "raisedBy": {"id", "name", "email"},
      "payer": {"kind": "customer"} | {"kind": "guarantee_letter", "issuer", "letterNumber", "amountCentavos"},
      "lines": [{"productId", "inventoryId", "code", "name", "unit", "quantity", "freeQuantity",
                 "unitPriceCentavos", "discountCentavos", "totalCentavos", "bundle", "vatCategory"}],
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

from modules import inprocess
from modules.crm.config import Settings
from modules.crm.tenants import company_header
from modules.crm.models import Company, Contact, Product, Quote, Team, User

TIMEOUT = 15  # seconds


class OrdersUnavailable(Exception):
    """Bishnoi One Order didn't answer, or refused: the message says which, for people."""


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


def division_of(db: Session, team: Team | None) -> dict | None:
    if team is None:
        return None
    top = db.get(Team, team.parent_id) if team.parent_id else team
    return {"id": top.id, "name": top.name} if top else None


def line_out(db: Session, line: dict) -> dict:
    """One priced line as the sales order takes it: the promo and the extra discount apart, and their sum as before."""
    product = db.get(Product, line.get("productId")) if line.get("productId") else None
    promo, extra = line.get("promoDiscountCentavos") or 0, line.get("discountCentavos") or 0
    return {
        "productId": line.get("productId"),
        "inventoryId": product.inventory_id if product else None,
        "code": line.get("productCode"),
        "name": line.get("productName"),
        "unit": line.get("unit"),
        "quantity": line.get("quantity", 0),
        "freeQuantity": line.get("freeQuantity", 0),
        "unitPriceCentavos": line.get("unitPriceCentavos", 0),
        "discountCentavos": promo + extra,
        "promoName": line.get("promoName"),
        "promoDiscountCentavos": promo,
        "extraDiscountCentavos": extra,
        "discountKind": line.get("discountKind"),
        "discountValue": line.get("discountValue"),
        "totalCentavos": line.get("totalCentavos", 0),
        "bundle": line.get("bundleName"),
        # Its VAT category, for the invoice made from its delivery (step 13).
        "vatCategory": product.vat_category if product else "standard",
    }


def customer_out(company: Company | None, contact: Contact | None, name: str) -> dict:
    customer = contact or company
    tin = (company.extra or {}).get("tin") if company is not None else None
    return {
        "kind": "contact" if contact else "company",
        "id": customer.id if customer else None,
        "name": name,
        "address": address_of(company),
        "email": text(customer, "email"),
        "phone": text(customer, "phone", "mobile"),
        "tin": tin.strip() if isinstance(tin, str) and tin.strip() else None,
    }


def payload(db: Session, quote: Quote, me: User, settings: Settings) -> dict:
    """What Bishnoi One Order receives for a quote. See the module's docstring."""
    contact = db.get(Contact, quote.contact_id) if quote.contact_id else None
    company = db.get(Company, quote.company_id) if quote.company_id else (contact.company if contact else None)
    team = db.get(Team, quote.team_id) if quote.team_id else None
    owner = db.get(User, quote.owner_id) if quote.owner_id else None
    letter = quote.letter or {}
    return {
        "source": "bishnoi-crm",
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
        # What it was priced with (2026-11-23): the sales order keeps and shows it.
        "pricing": {"priceType": quote.price_type, "priceTypeName": quote.price_type_name, "rx": quote.rx, "terms": quote.terms,
                    "approvalReasons": list(quote.approval_reasons or []), "warnings": []},
        "customer": customer_out(company, contact, quote.customer_name),
        "team": {"id": team.id, "name": team.name} if team else None,
        # The division the team sits under (the org chart: step 4), for revenue by division.
        "division": division_of(db, team),
        "salesperson": person(owner),
        "raisedBy": person(me),
        "payer": (
            {"kind": "guarantee_letter", "issuer": quote.payer_name, "letterNumber": letter.get("number"), "amountCentavos": letter.get("amountCentavos")}
            if quote.payer != "self"
            else {"kind": "customer"}
        ),
        "letter": ({"number": letter.get("number"), "issuedOn": letter.get("issuedOn"), "amountCentavos": letter.get("amountCentavos"),
                    "fileName": (letter.get("file") or {}).get("name")} if quote.payer != "self" else None),
        "lines": [line_out(db, line) for line in quote.lines],
        "totals": {
            "grossCentavos": quote.gross_centavos,
            "promoDiscountCentavos": quote.promo_discount_centavos,
            "discountCentavos": quote.discount_centavos,
            "totalCentavos": quote.total_centavos,
        },
        "tax": quote.tax,
        "currency": settings.org_currency,
    }


def direct_payload(db: Session, me: User, settings: Settings, *, company: Company | None, contact: Contact | None, customer_name: str,
                   priced: dict, kind, rx: bool, notes: str | None, terms: str | None, issuer, letter: dict | None, warnings: list[str]) -> dict:
    """A sales order made directly with the quote form (2026-11-23): the same payload as a quote's, without a quote.
    The person making it is its salesperson, as they own a quote they make."""
    team = me.team
    return {
        "source": "bishnoi-crm",
        "quote": None,
        "pricing": {"priceType": kind.code, "priceTypeName": kind.name, "rx": rx, "notes": notes, "terms": terms,
                    "approvalReasons": list(priced.get("approvalReasons") or []), "warnings": warnings},
        "customer": customer_out(company, contact, customer_name),
        "team": {"id": team.id, "name": team.name} if team else None,
        "division": division_of(db, team),
        "salesperson": person(me),
        "raisedBy": person(me),
        "payer": ({"kind": "guarantee_letter", "issuer": issuer.name, "letterNumber": letter["number"], "amountCentavos": letter["amountCentavos"]}
                  if issuer is not None and letter else {"kind": "customer"}),
        "letter": letter if issuer is not None else None,
        "lines": [line_out(db, line) for line in priced["lines"]],
        "totals": {"grossCentavos": priced["grossCentavos"], "promoDiscountCentavos": priced["promoDiscountCentavos"],
                   "discountCentavos": priced["discountCentavos"], "totalCentavos": priced["totalCentavos"]},
        "tax": priced.get("tax"),
        "currency": settings.org_currency,
    }


def place_direct(settings: Settings, body: dict) -> dict:
    """Makes the direct order in Inventory (its /integration/sales-orders) and returns {id, number, status}."""
    if not settings.inventory_api_url:
        raise OrdersUnavailable("Inventory isn't linked, so a sales order can't be made here.")
    try:
        answer = inprocess.post("crm", f"{settings.inventory_api_url.rstrip('/')}/integration/sales-orders", json=body, timeout=TIMEOUT,
                                headers={**inprocess.key_header(settings.inventory_api_key), **company_header(settings)})
    except Exception as e:  # noqa: BLE001 (any failure to reach it reads the same to people)
        raise OrdersUnavailable("Inventory can't be reached right now. Try again in a moment.") from e
    if answer.status_code in (409, 422):
        detail = answer.json().get("detail")
        raise OrdersUnavailable(detail if isinstance(detail, str) else "Inventory refused the order: check the warehouse.")
    if answer.status_code >= 300:
        raise OrdersUnavailable(f"Inventory answered with an error ({answer.status_code}).")
    return answer.json()


def send(settings: Settings, quote_id: str, body: dict) -> dict:
    """POSTs the order to Bishnoi One Order and returns what it made."""
    request = urllib.request.Request(
        f"{settings.orders_api_url.rstrip('/')}/orders",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            **inprocess.key_header(settings.orders_api_key),
            "Idempotency-Key": quote_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            **company_header(settings),
        },
    )
    try:
        with inprocess.urlopen("crm", request, timeout=TIMEOUT) as response:  # noqa: S310 (the address is ours, from settings)
            made = json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise OrdersUnavailable("Order service connection could not be authenticated. Please contact your system administrator.") from e
        detail = ""
        try:
            detail = json.loads(e.read() or b"{}").get("detail") or ""
        except (ValueError, AttributeError):
            pass
        message = f"Bishnoi One Order didn't take the order ({e.code})."
        raise OrdersUnavailable(f"{message} {detail}".strip() if isinstance(detail, str) else message) from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise OrdersUnavailable("Bishnoi One Order can't be reached right now. Try again in a moment.") from e
    if not isinstance(made, dict) or not made.get("id") or not made.get("number"):
        raise OrdersUnavailable("Bishnoi One Order answered without an order number.")
    return made
