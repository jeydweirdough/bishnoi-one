"""Price approvals: every product's price is Finance's.

What waits, read from Bishnoi One CRM each time (nothing is kept here):

- prices a manager set in the CRM (a Doctor's, Patient's or Special price, for
  the company or one division): salespeople don't see one until it's approved;
- quotes at a price a rep asked for: they don't go out until approved.

prices.view to see them, prices.approve to decide. The decision is the CRM's
to keep; Finance's activity log notes who made it.
"""

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import Field

from app.access import access_of, permitted
from app.api import Api
from app.audit import audit
from app.crm import CrmUnavailable, decide_price, decide_quote, waiting_prices
from app.deps import DB, SettingsDep

router = APIRouter(prefix="/finance/prices", tags=["prices"])


def crm_says(e: CrmUnavailable) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.get("/waiting")
def waiting(user: permitted("prices.view"), settings: SettingsDep) -> dict:
    try:
        found = waiting_prices(settings)
    except CrmUnavailable as e:
        raise crm_says(e) from None
    return found | {"canApprove": access_of(user).can("prices.approve")}


class PriceDecision(Api):
    kind: Literal["product", "team"]
    product_id: str = Field(min_length=1, max_length=36)
    price_type_code: str = Field(min_length=1, max_length=40)
    team_id: str | None = Field(None, max_length=36)
    decision: Literal["approve", "reject"]
    reason: str | None = Field(None, max_length=500)
    # For the activity log: what it was, as the screen showed it.
    label: str = Field("a price", max_length=300)


@router.post("/decide")
def decide_a_price(user: permitted("prices.approve"), db: DB, settings: SettingsDep, body: PriceDecision) -> dict:
    if body.decision == "reject" and not body.reason:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Say why it's rejected: the manager sees your reason.")
    sent = body.model_dump(by_alias=True, exclude={"label"}) | {"byName": user.full_name}
    try:
        decide_price(settings, sent)
    except CrmUnavailable as e:
        raise crm_says(e) from None
    audit(db, user, f"price.{body.decision}d", target=body.label, target_type="price")
    db.commit()
    return {"ok": True, "decision": body.decision}


class QuoteDecision(Api):
    decision: Literal["approve", "reject"]
    note: str | None = Field(None, max_length=1000)
    number: str = Field("a quote", max_length=40)


@router.post("/quotes/{quote_id}/decide")
def decide_a_quote(user: permitted("prices.approve"), db: DB, settings: SettingsDep, quote_id: str, body: QuoteDecision) -> dict:
    if body.decision == "reject" and not body.note:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Say why it's rejected: the rep sees your reason on the quote.")
    try:
        decide_quote(settings, quote_id, {"decision": body.decision, "note": body.note, "byName": user.full_name})
    except CrmUnavailable as e:
        raise crm_says(e) from None
    audit(db, user, f"quote_price.{body.decision}d", target=body.number, target_type="quote")
    db.commit()
    return {"ok": True, "decision": body.decision}
