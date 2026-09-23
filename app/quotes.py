"""Quotes: a customer's priced request, with an optional guarantee letter.

A quote is a child record of a customer. It carries the customer's scope, and
moves and is deleted with it (CHILD_TYPES in app/routers/sales.py). Reps make
quotes in the sales workspace; Finance approves special prices and big
discounts, checks guarantee letters and records what the issuer has paid
(app/routers/finance.py). Prices are copied onto the quote when it's made, so
later price changes never rewrite an old quote.

Finance's work is tracked in three top-level fields so it can be queried:
    approvalStatus  none | pending | approved | rejected
    letterStatus    none | pending | verified | rejected
    paymentStatus   none | unpaid | partial | paid
"""

import re

from fastapi import HTTPException, Response, status

from app.models import Profile
from app.pricing import SELF, PricedQuote
from app.schemas import QuoteIn
from app.scope import Scope
from app.store.files import FileStore

QUOTE = "quote"


def quote_number(quote_id: str) -> str:
    return "Q-" + quote_id.replace("-", "")[:8].upper()


def quote_doc(
    *,
    quote_id: str,
    scope: Scope,
    customer: dict,
    quote: QuoteIn,
    priced: PricedQuote,
    payer_name: str | None,
    letter_file: dict | None,
    user: Profile,
    now: str,
) -> dict:
    with_letter = quote.payer != SELF
    doc = {
        "_id": quote_id,
        "_type": QUOTE,
        **scope.stamp(),
        "customerId": customer["_id"],
        "customerName": customer["name"],
        "number": quote_number(quote_id),
        "priceType": priced.price_type.code,
        "priceTypeName": priced.price_type.name,
        "rx": quote.rx,
        "payer": quote.payer,
        "payerName": payer_name,
        "notes": quote.notes,
        "lines": [
            {
                "_key": f"line{i}",  # Sanity wants a key on every object in an array
                "productId": line.product_id,
                "productCode": line.product_code,
                "productName": line.product_name,
                "unit": line.unit,
                "quantity": line.quantity,
                "freeQuantity": line.free_quantity,
                "unitPriceCentavos": line.unit_price,
                "grossCentavos": line.gross,
                "promoId": line.promo_id,
                "promoName": line.promo_name,
                "promoDiscountCentavos": line.promo_discount,
                "discountKind": line.discount_kind,
                "discountValue": line.discount_value,
                "discountCentavos": line.discount,
                "totalCentavos": line.total,
                # Copied, like everything else here: editing a bundle later
                # never changes a quote already given.
                "bundleId": line.bundle_id,
                "bundleName": line.bundle_name,
                "contents": line.contents,
            }
            for i, line in enumerate(priced.lines)
        ],
        "grossCentavos": priced.gross,
        "promoDiscountCentavos": priced.promo_discount,
        "discountCentavos": priced.discount,
        "totalCentavos": priced.total,
        "approvalStatus": "pending" if priced.approval_reasons else "none",
        "approvalReasons": list(priced.approval_reasons),
        "letterStatus": "pending" if with_letter else "none",
        "paymentStatus": "unpaid" if with_letter else "none",
        "paidCentavos": 0,
        "payments": [],
        "createdAt": now,
        "createdById": user.id,
        "createdByName": user.full_name,
    }
    if with_letter and quote.letter:
        doc["letter"] = {
            "number": quote.letter.number,
            "issuedOn": quote.letter.issued_on.isoformat(),
            "amountCentavos": quote.letter.amount_centavos,
            "file": letter_file,
        }
    return {k: v for k, v in doc.items() if v is not None}


def priced_out(priced: PricedQuote) -> dict:
    """A preview: what the quote would come to, before it's saved."""
    return {
        "priceType": priced.price_type.code,
        "lines": [
            {
                "productId": line.product_id,
                "productCode": line.product_code,
                "productName": line.product_name,
                "quantity": line.quantity,
                "freeQuantity": line.free_quantity,
                "unitPriceCentavos": line.unit_price,
                "grossCentavos": line.gross,
                "promoDiscountCentavos": line.promo_discount,
                "discountCentavos": line.discount,
                "totalCentavos": line.total,
                # A bundle's line: one for the whole set, or one of several its
                # price was shared across. `contents` is filled only on a set.
                "bundleId": line.bundle_id,
                "bundleName": line.bundle_name,
                "contents": line.contents,
            }
            for line in priced.lines
        ],
        "grossCentavos": priced.gross,
        "promoDiscountCentavos": priced.promo_discount,
        "discountCentavos": priced.discount,
        "totalCentavos": priced.total,
        "approvalReasons": list(priced.approval_reasons),
    }


def state(doc: dict) -> str:
    """rejected, waiting (on Finance), or ready."""
    statuses = (doc.get("approvalStatus"), doc.get("letterStatus"))
    if "rejected" in statuses:
        return "rejected"
    if "pending" in statuses:
        return "waiting"
    return "ready"


def finance_has_acted(doc: dict) -> bool:
    return (
        doc.get("approvalStatus") in ("approved", "rejected")
        or doc.get("letterStatus") in ("verified", "rejected")
        or bool(doc.get("payments"))
    )


def _person(doc: dict, prefix: str) -> dict | None:
    return {"id": doc[f"{prefix}ById"], "name": doc.get(f"{prefix}ByName")} if doc.get(f"{prefix}ById") else None


def quote_out(doc: dict, *, division_name: str, team_name: str, customer_name: str | None, can: dict) -> dict:
    scope = Scope.of(doc)
    letter = doc.get("letter")
    return {
        "id": doc["_id"],
        "rev": doc.get("_rev"),
        "number": doc["number"],
        "division": scope.division,
        "divisionName": division_name,
        "team": scope.subdivision,
        "teamName": team_name,
        "customerId": doc["customerId"],
        "customerName": customer_name or doc.get("customerName"),
        "priceType": doc["priceType"],
        "priceTypeName": doc["priceTypeName"],
        "rx": doc.get("rx", False),
        "payer": doc["payer"],
        "payerName": doc.get("payerName"),
        "notes": doc.get("notes"),
        "lines": doc["lines"],
        "grossCentavos": doc["grossCentavos"],
        "promoDiscountCentavos": doc["promoDiscountCentavos"],
        "discountCentavos": doc["discountCentavos"],
        "totalCentavos": doc["totalCentavos"],
        "state": state(doc),
        "approval": {
            "status": doc["approvalStatus"],
            "reasons": doc.get("approvalReasons", []),
            "note": doc.get("approvalNote"),
            "by": _person(doc, "approval"),
            "at": doc.get("approvalAt"),
        },
        "letter": (
            {
                "number": letter["number"],
                "issuedOn": letter["issuedOn"],
                "amountCentavos": letter["amountCentavos"],
                "file": (
                    {k: letter["file"][k] for k in ("name", "contentType", "size")} if letter.get("file") else None
                ),
                "status": doc["letterStatus"],
                "note": doc.get("letterNote"),
                "by": _person(doc, "letter"),
                "at": doc.get("letterAt"),
            }
            if letter
            else None
        ),
        "payment": {
            "status": doc["paymentStatus"],
            "paidCentavos": doc.get("paidCentavos", 0),
            "payments": doc.get("payments", []),
        },
        "createdAt": doc["createdAt"],
        "createdBy": {"id": doc.get("createdById"), "name": doc.get("createdByName")},
        "can": can,
    }


def letter_file_ref(doc: dict) -> str | None:
    file = (doc.get("letter") or {}).get("file")
    return file.get("ref") if file else None


def letter_response(doc: dict, files: FileStore) -> Response:
    file = (doc.get("letter") or {}).get("file")
    data = files.read(file["ref"]) if file else None
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This quote has no guarantee letter file.")
    name = re.sub(r"[^A-Za-z0-9._-]", "", f"{doc['number']}-guarantee-letter.{file['ext']}")
    return Response(
        data,
        media_type=file["contentType"],
        headers={"Content-Disposition": f'inline; filename="{name}"', "X-Content-Type-Options": "nosniff"},
    )
