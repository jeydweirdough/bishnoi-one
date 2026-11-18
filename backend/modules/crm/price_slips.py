"""Team prices and special prices on approval slips (Step 4C, 2026-11-18).

A manager's price proposal (a team's own price, or a company special price such as Doctor's or Patient's) still goes
to Finance exactly as before (routers/prices.py decide_price, Finance's Price approvals screen through
routers/integration_prices.py): Finance's queue, rules and decision are unchanged. It also opens one approval slip on
the Platform per save (approval.requested, kind "price_change"), signed up the proposer's org chart; Finance's
approval is attached to it as a link.

The gate is the CRM's own (decided: Finance stays as it is): a proposed price goes live only when Finance approved it
AND its slip is signed, in whichever order they happen.

    Finance approves first   ──▶  its decision is kept on the row (slip_held_centavos); the price in use stays
    the slip signs           ──▶  what Finance approved goes live; a price Finance hasn't decided yet goes live
                                  as soon as Finance approves it (as today)
    the slip is returned     ──▶  a proposal still waiting for Finance is withdrawn (the price in use stays);
                                  one Finance already approved is dropped
    Finance rejects          ──▶  as today; the slip has nothing left to make live

A price Finance sets itself never needs a slip. Standalone (no Platform), no slip is opened and Finance alone decides.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.crm import business_events
from modules.crm.models import PriceType, Product, ProductPrice, Team, TeamPrice, User

KIND = "price_change"
FINANCE_LINK = {"label": "Finance price approval (Price approvals in Finance)", "app": "finance", "kind": "price_approval", "url": "/finance/prices"}


def _slug() -> str | None:
    settings = business_events._state.get("settings")
    return getattr(settings, "company", None) if settings is not None else None


def connected() -> bool:
    """Connected to Bishnoi One (PLATFORM_API_URL): slips are signed there. Standalone, Finance alone decides, as before."""
    settings = business_events._state.get("settings")
    return bool(getattr(settings, "platform_api_url", None))


def ask(db: Session, me: User, rows: list[ProductPrice | TeamPrice], *, team: Team | None = None) -> str | None:
    """One slip for the prices just proposed (rows waiting for Finance). Returns the slip's batch id."""
    rows = [r for r in rows if r.approval_status == "pending"]
    if not rows or not connected():
        return None
    db.flush()
    batch = str(uuid.uuid4())
    before = {r.slip_batch_id for r in rows if r.slip_batch_id}
    for r in rows:
        r.slip_batch_id, r.slip_state, r.slip_held_centavos = batch, "pending", None
    db.flush()
    for old in before:  # an earlier slip left with nothing on it is withdrawn
        if not _rows(db, old):
            business_events.emit(db, _slug(), "approval.withdrawn", {"kind": KIND, "id": old, "reason": "Its prices were proposed again.", "by": me.email})
    names = {p.id: p.name for p in db.scalars(select(Product).where(Product.id.in_({r.product_id for r in rows})))}
    types = {t.code: t.name for t in db.scalars(select(PriceType))}
    lines = [{"name": f"{names.get(r.product_id, 'Product')} · {types.get(r.price_type_code, r.price_type_code)}",
              "quantity": 1, "totalCentavos": r.proposed_amount_centavos or 0,
              "soldAs": "Take the price away" if r.proposed_amount_centavos == 0 else (f"Now {r.amount_centavos / 100:,.2f}" if r.amount_centavos else "New price")}
             for r in rows[:30]]
    where = f"team {team.name}" if team else "the company price list"
    business_events.emit(db, _slug(), "approval.requested", {
        "kind": KIND, "id": batch, "number": None,
        "title": f"Price change for {where}: {len(rows)} price{'s' if len(rows) != 1 else ''}",
        "url": f"/crm/prices?team={team.id}" if team else "/crm/products",
        "requester": {"identityId": me.platform_identity_id, "email": me.email, "name": me.full_name},
        "summary": {"customer": None, "lines": lines, "moreLines": max(0, len(rows) - len(lines)), "currency": "PHP",
                    "notes": "Finance approves the amounts as before; the prices go live once Finance has approved them and this slip is signed."},
        "attachments": [FINANCE_LINK],
    })
    return batch


def _rows(db: Session, batch: str) -> list[ProductPrice | TeamPrice]:
    return [*db.scalars(select(ProductPrice).where(ProductPrice.slip_batch_id == batch)),
            *db.scalars(select(TeamPrice).where(TeamPrice.slip_batch_id == batch))]


def waits_for_slip(x: ProductPrice | TeamPrice) -> bool:
    return x.slip_state == "pending"


def hold(x: ProductPrice | TeamPrice) -> None:
    """Finance approved while the slip waits: the decision is kept; the price in use stays until the slip signs."""
    x.slip_held_centavos = x.proposed_amount_centavos if x.proposed_amount_centavos is not None else x.amount_centavos
    x.proposed_amount_centavos = None
    x.approval_status = "approved"
    x.rejection_reason = None


def cleared(x: ProductPrice | TeamPrice) -> None:
    """Finance set the price itself: no slip stands for it any more."""
    x.slip_batch_id = x.slip_state = None
    x.slip_held_centavos = None


def decided(db: Session, data: dict) -> None:
    """The slip's end (approval.decided)."""
    batch = str(data.get("id") or "")
    number = str((data.get("approval") or {}).get("number") or "")
    for x in _rows(db, batch):
        if x.slip_state != "pending":
            continue
        if data.get("decision") == "approved":
            x.slip_state = "signed"
            if x.slip_held_centavos is not None:
                held, x.slip_held_centavos = x.slip_held_centavos, None
                if held == 0:
                    db.delete(x)  # the proposal was to take the price away
                    continue
                x.amount_centavos = held
        elif data.get("decision") == "returned":
            x.slip_state, x.slip_held_centavos = "returned", None
            if x.approval_status == "pending":
                x.proposed_amount_centavos = None
                x.approval_status = "approved" if x.amount_centavos > 0 else "rejected"
                note = str(data.get("note") or "")
                x.rejection_reason = (f"Returned on approval slip {number}: {note}" if number else f"Returned: {note}")[:500]

