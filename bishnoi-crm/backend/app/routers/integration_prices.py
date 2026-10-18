"""Finance's price approvals: what waits for Bishnoi One Finance, and its decisions.

Every product's price is Finance's to curate. A price a manager sets in the CRM
(a Doctor's, Patient's or Special price, for the company or for one division)
waits as a proposal until Finance approves it, and salespeople don't see it
until then (app/pricing.py prices with approved prices only). A quote at a
price the rep asked for waits for Finance too, not the team lead.

Finance's people approve in their own app, where they aren't CRM users, so the
app says who decided (byName) and the CRM keeps that name. Only the Finance
app's key is taken (X-Bishnoi-Key, as in app/routers/integration.py).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field
from sqlalchemy import select

from app import mail
from app.api import Api, not_found
from app.audit import audit
from app.deps import DB, SettingsDep
from app.models import ProductPrice, Quote, Team, User
from app.routers.integration import calling_app
from app.routers.prices import PriceDecisionIn, decide_price, pending_items
from app.routers.quotes import Decision, apply_decision, decided, finance_decides


def finance_app(caller: Annotated[str, Depends(calling_app)]) -> str:
    if caller != "finance":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only Bishnoi One Finance decides prices.")
    return caller


Finance = Annotated[str, Depends(finance_app)]
router = APIRouter(prefix="/integration/prices", tags=["integration"])


def srp_of(db, product_ids: set[str]) -> dict[str, int]:
    """Each product's approved SRP, to set a requested price against."""
    rows = db.scalars(
        select(ProductPrice).where(ProductPrice.product_id.in_(product_ids), ProductPrice.price_type_code == "SRP", ProductPrice.approval_status == "approved")
    )
    return {r.product_id: r.amount_centavos for r in rows if r.amount_centavos > 0}


def quotes_waiting(db, settings) -> list[dict]:
    """Quotes at a price the rep asked for, waiting for Finance: oldest first, as they came in."""
    waiting = [q for q in db.scalars(select(Quote).where(Quote.approval_status == "pending").order_by(Quote.created_at)) if finance_decides(q)]
    srp = srp_of(db, {l.get("productId") for q in waiting for l in q.lines or [] if l.get("productId")})
    teams = {t.id: t.name for t in db.scalars(select(Team))}
    users = {u.id: u.full_name for u in db.scalars(select(User))}
    base = (settings.crm_app_url or "").rstrip("/")
    return [
        {
            "id": q.id,
            "number": q.number,
            "customerName": q.customer_name,
            "teamName": teams.get(q.team_id, "No division"),
            "repName": users.get(q.owner_id, "A rep"),
            "priceTypeName": q.price_type_name,
            "reasons": q.approval_reasons,
            "notes": q.notes,
            "grossCentavos": q.gross_centavos,
            "totalCentavos": q.total_centavos,
            "createdAt": q.created_at.isoformat(),
            "url": f"{base}/quotes/{q.id}" if base else None,
            "lines": [
                {
                    "productCode": l.get("productCode"),
                    "productName": l.get("productName") or l.get("bundleName"),
                    "quantity": l.get("quantity"),
                    "unitPriceCentavos": l.get("unitPriceCentavos"),
                    "srpCentavos": srp.get(l.get("productId")),
                    "totalCentavos": l.get("totalCentavos"),
                }
                for l in q.lines or []
            ],
        }
        for q in waiting
    ]


@router.get("")
def waiting_for_finance(_: Finance, db: DB, settings: SettingsDep) -> dict:
    """Everything Finance has to decide: proposed prices, and quotes at requested prices."""
    prices = pending_items(db)
    quotes = quotes_waiting(db, settings)
    return {"prices": prices, "quotes": quotes, "total": len(prices) + len(quotes)}


class FinancePriceDecision(PriceDecisionIn):
    by_name: str = Field(min_length=1, max_length=120)


@router.post("/decide")
def decide_a_price(_: Finance, db: DB, body: FinancePriceDecision) -> dict:
    decide_price(db, body, by_id=None, by_name=body.by_name)
    audit(db, f"{body.by_name} (Finance)", f"price.{body.decision}d", target=f"{body.kind} price {body.price_type_code} for product {body.product_id}", target_type="price")
    db.commit()
    return {"ok": True, "decision": body.decision}


class FinanceQuoteDecision(Decision):
    by_name: str = Field(min_length=1, max_length=120)


@router.post("/quotes/{quote_id}/decide")
def decide_a_quote(_: Finance, db: DB, settings: SettingsDep, quote_id: str, body: FinanceQuoteDecision) -> dict:
    quote = db.get(Quote, quote_id)
    if quote is None:
        raise not_found("quote")
    if quote.approval_status != "pending" or not finance_decides(quote):
        raise HTTPException(status.HTTP_409_CONFLICT, "This quote isn't waiting for Finance.")
    decided(body)
    name = f"{body.by_name} (Finance)"
    apply_decision(quote, body, by_id=None, by_name=name)
    audit(db, name, f"quote.{quote.approval_status}", target=quote.number, target_type="quote", target_id=quote.id)
    db.commit()
    mail.quote_decided(db, settings, quote, name)
    return {"ok": True, "decision": body.decision, "status": quote.approval_status}
