"""Prices: what one team charges, over the company's price list.

A team's own price stands over the company's only where it set one, so a team
that sets nothing prices exactly as before. It may also narrow the price types
it quotes with; choosing none means every one there is.

Special prices set by managers (such as Doctor's Price, Patient's Price, or team
overrides) require Finance approval before they become visible to salespersons.

Needs products.prices, for a team within the person's reach: any team with
the "all" scope, otherwise their own.
"""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.access import Access, require
from app.api import Api, field_error, not_found
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import PriceType, Product, ProductPrice, Team, TeamPrice, TeamPriceType, User

router = APIRouter(prefix="/prices", tags=["prices"])

SetPrices = Annotated[Access, Depends(require("products.prices"))]


def is_finance_user(access: Access, me: User) -> bool:
    """Finance (products.approve), or an Administrator. Finance's people mostly
    decide in Bishnoi One Finance (app/routers/integration_prices.py)."""
    return access.can("products.approve") or (access.scope == "all" and "admin.settings" in access.permissions)


def teams_for(db: Session, access: Access) -> list[Team]:
    """The teams this person may price."""
    query = select(Team).where(Team.is_active).order_by(Team.name)
    if access.scope != "all":
        query = query.where(Team.id.in_(access.team_ids or {access.team_id or ""}))
    return list(db.scalars(query))


def get_team(db: Session, access: Access, team_id: str) -> Team:
    team = next((t for t in teams_for(db, access) if t.id == team_id), None)
    if team is None:
        raise not_found("team")
    return team


def sheet_out(db: Session, team: Team) -> dict:
    types = list(db.scalars(select(PriceType).where(PriceType.is_active).order_by(PriceType.sort_order, PriceType.name)))
    chosen = set(db.scalars(select(TeamPriceType.price_type_code).where(TeamPriceType.team_id == team.id)))
    own_rows = {(p.product_id, p.price_type_code): p for p in db.scalars(select(TeamPrice).where(TeamPrice.team_id == team.id))}
    listed = [t.code for t in types if t.entry == "list"]
    products = db.scalars(select(Product).where(Product.is_active).order_by(Product.name)).all()
    return {
        "team": team.id,
        "teamName": team.name,
        "usesAllTypes": not chosen,
        "priceTypes": [{"code": t.code, "name": t.name, "entry": t.entry, "rule": t.rule, "chosen": t.code in chosen} for t in types],
        "products": [
            {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "unit": p.unit,
                "prices": {
                    code: {
                        "company": company.get(code),
                        "team": (
                            row.amount_centavos
                            if row and row.approval_status == "approved"
                            else (row.proposed_amount_centavos if row else None)
                        ),
                        "teamStatus": row.approval_status if row else "approved",
                        "teamApproved": row.amount_centavos if row and row.approval_status == "approved" else None,
                        "teamProposed": row.proposed_amount_centavos if row else None,
                    }
                    for code in listed
                    for row in [own_rows.get((p.id, code))]
                    for company in [{x.price_type_code: x.amount_centavos for x in p.prices if x.approval_status == "approved"}]
                },
            }
            for p in products
        ],
    }


@router.get("/teams")
def list_teams(access: SetPrices, db: DB) -> list[dict]:
    return [{"id": t.id, "name": t.name} for t in teams_for(db, access)]


def pending_items(db: Session) -> list[dict]:
    """Every company and team price waiting for Finance, newest first."""
    users_map = {u.id: u.full_name for u in db.scalars(select(User)).all()}
    prods_map = {p.id: p for p in db.scalars(select(Product)).all()}
    teams_map = {t.id: t.name for t in db.scalars(select(Team)).all()}
    types_map = {pt.code: pt.name for pt in db.scalars(select(PriceType)).all()}

    def row(kind: str, x: ProductPrice | TeamPrice, team_id: str | None) -> dict | None:
        p = prods_map.get(x.product_id)
        if not p:
            return None
        return {
            "id": f"{kind}_{team_id + '_' if team_id else ''}{x.product_id}_{x.price_type_code}",
            "kind": kind,
            "productId": x.product_id,
            "productCode": p.code,
            "productName": p.name,
            "unit": p.unit,
            "teamId": team_id,
            "teamName": teams_map.get(team_id, "Division") if team_id else "Company price (every division)",
            "priceTypeCode": x.price_type_code,
            "priceTypeName": types_map.get(x.price_type_code, x.price_type_code),
            "currentAmountCentavos": x.amount_centavos if x.amount_centavos > 0 else None,
            # 0: the proposal is to take the price away.
            "proposedAmountCentavos": x.proposed_amount_centavos,
            "submittedById": x.submitted_by_id,
            "submittedByName": users_map.get(x.submitted_by_id, "A manager"),
            "submittedAt": x.submitted_at.isoformat() if x.submitted_at else None,
        }

    rows = [row("product", pp, None) for pp in db.scalars(select(ProductPrice).where(ProductPrice.approval_status == "pending"))]
    rows += [row("team", tp, tp.team_id) for tp in db.scalars(select(TeamPrice).where(TeamPrice.approval_status == "pending"))]
    return sorted((r for r in rows if r), key=lambda r: r["submittedAt"] or "", reverse=True)


@router.get("/pending-approvals")
def list_pending_price_approvals(access: SetPrices, me: CurrentUser, db: DB) -> dict:
    """Lists all product prices and team prices awaiting Finance approval."""
    items = pending_items(db)
    return {"items": items, "total": len(items), "canApprove": is_finance_user(access, me)}


class PriceDecisionIn(Api):
    kind: Literal["product", "team"]
    product_id: str
    price_type_code: str
    team_id: str | None = None
    decision: Literal["approve", "reject"]
    reason: str | None = None


def decide_price(
    db: Session, body: "PriceDecisionIn", *, by_id: str | None, by_name: str
) -> None:
    """Approves (the proposed amount becomes the price) or rejects (the price stays as it was)."""
    if body.kind == "team" and not body.team_id:
        raise field_error("teamId", "Team ID is required for team price approvals.")
    x = db.get(ProductPrice, (body.product_id, body.price_type_code)) if body.kind == "product" else db.get(TeamPrice, (body.team_id, body.product_id, body.price_type_code))
    if not x or x.approval_status != "pending":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This price proposal is not pending approval.")
    now = datetime.now(UTC)
    if body.decision == "approve":
        if x.proposed_amount_centavos == 0:
            db.delete(x)  # the proposal was to take the price away
        else:
            x.amount_centavos = x.proposed_amount_centavos or x.amount_centavos
            x.proposed_amount_centavos = None
            x.approval_status = "approved"
            x.rejection_reason = None
    elif x.amount_centavos > 0:
        # Rejected: the price in use stays; the proposal goes.
        x.proposed_amount_centavos = None
        x.approval_status = "approved"
        x.rejection_reason = body.reason or "Rejected by Finance"
    else:
        # A new price, rejected: there's nothing to keep.
        x.approval_status = "rejected"
        x.rejection_reason = body.reason or "Rejected by Finance"
    if x in db:
        x.approved_by_id, x.approved_by_name, x.approved_at = by_id, by_name, now


@router.post("/approvals/decide")
def decide_price_approval(access: SetPrices, me: CurrentUser, db: DB, body: PriceDecisionIn) -> dict:
    if not is_finance_user(access, me):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only Finance or an Administrator can approve product prices.")
    decide_price(db, body, by_id=me.id, by_name=me.full_name)
    audit(db, me, f"price.{body.decision}d", target=f"{body.kind} price {body.price_type_code} for product {body.product_id}", target_type="price")
    db.commit()
    return {"ok": True, "decision": body.decision}


@router.get("")
def read_sheet(access: SetPrices, db: DB, team: str = Query(max_length=36)) -> dict:
    return sheet_out(db, get_team(db, access, team))


class TypesIn(Api):
    codes: list[str] = Field(max_length=50)


@router.put("/types")
def choose_types(access: SetPrices, me: CurrentUser, db: DB, body: TypesIn, team: str = Query(max_length=36)) -> dict:
    found = get_team(db, access, team)
    known = set(db.scalars(select(PriceType.code).where(PriceType.is_active)))
    if any(c not in known for c in body.codes):
        raise field_error("codes", "Pick price types from the list.")
    db.execute(delete(TeamPriceType).where(TeamPriceType.team_id == found.id))
    for code in dict.fromkeys(body.codes):
        db.add(TeamPriceType(team_id=found.id, price_type_code=code))
    audit(db, me, "team_prices.types_set", target=found.name, target_type="team", target_id=found.id)
    db.commit()
    return sheet_out(db, found)


class PriceIn(Api):
    product_id: str = Field(max_length=36)
    price_type_code: str = Field(max_length=40)
    # None hands this price back to the company's.
    amount_centavos: int | None = Field(None, ge=1, lt=10**11)


class PricesIn(Api):
    items: list[PriceIn] = Field(max_length=5000)


@router.put("")
def set_prices(access: SetPrices, me: CurrentUser, db: DB, body: PricesIn, team: str = Query(max_length=36)) -> dict:
    found = get_team(db, access, team)
    listed = set(db.scalars(select(PriceType.code).where(PriceType.entry == "list")))
    products = set(db.scalars(select(Product.id)))
    finance = is_finance_user(access, me)
    now = datetime.now(UTC)
    for n, item in enumerate(body.items):
        if item.product_id not in products or item.price_type_code not in listed:
            raise field_error(f"items.{n}", "That product or price type isn't in the price list.")
        there = db.get(TeamPrice, (found.id, item.product_id, item.price_type_code))
        if finance:
            if item.amount_centavos is None:
                if there:
                    db.delete(there)
            elif there:
                there.amount_centavos = item.amount_centavos
                there.proposed_amount_centavos = None
                there.approval_status = "approved"
                there.approved_by_id = me.id
                there.approved_at = now
                there.rejection_reason = None
            else:
                db.add(TeamPrice(
                    team_id=found.id,
                    product_id=item.product_id,
                    price_type_code=item.price_type_code,
                    amount_centavos=item.amount_centavos,
                    approval_status="approved",
                    approved_by_id=me.id,
                    approved_at=now,
                ))
        else:
            # Manager setting team price: requires Finance approval!
            if item.amount_centavos is None:
                if there and there.approval_status == "pending":
                    if there.amount_centavos == 0:
                        db.delete(there)
                    else:
                        there.approval_status = "approved"
                        there.proposed_amount_centavos = None
                elif there:
                    there.proposed_amount_centavos = 0
                    there.approval_status = "pending"
                    there.submitted_by_id = me.id
                    there.submitted_at = now
            elif there:
                there.proposed_amount_centavos = item.amount_centavos
                there.approval_status = "pending"
                there.submitted_by_id = me.id
                there.submitted_at = now
                there.rejection_reason = None
            else:
                db.add(TeamPrice(
                    team_id=found.id,
                    product_id=item.product_id,
                    price_type_code=item.price_type_code,
                    amount_centavos=0,
                    approval_status="pending",
                    proposed_amount_centavos=item.amount_centavos,
                    submitted_by_id=me.id,
                    submitted_at=now,
                ))
    if body.items:
        audit(db, me, "team_prices.set" if finance else "team_prices.submitted_for_approval", target=found.name, target_type="team", target_id=found.id)
        db.commit()
    return sheet_out(db, found)
