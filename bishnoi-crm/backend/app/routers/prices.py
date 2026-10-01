"""Prices: what one team charges, over the company's price list.

A team's own price stands over the company's only where it set one, so a team
that sets nothing prices exactly as before. It may also narrow the price types
it quotes with; choosing none means every one there is.

Needs products.prices, for a team within the person's reach: any team with
the "all" scope, otherwise their own.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.access import Access, require
from app.api import Api, field_error, not_found
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import PriceType, Product, Team, TeamPrice, TeamPriceType

router = APIRouter(prefix="/prices", tags=["prices"])

SetPrices = Annotated[Access, Depends(require("products.prices"))]


def teams_for(db: Session, access: Access) -> list[Team]:
    """The teams this person may price."""
    query = select(Team).where(Team.is_active).order_by(Team.name)
    if access.scope != "all":
        query = query.where(Team.id == (access.team_id or ""))
    return list(db.scalars(query))


def get_team(db: Session, access: Access, team_id: str) -> Team:
    team = next((t for t in teams_for(db, access) if t.id == team_id), None)
    if team is None:
        raise not_found("team")
    return team


def sheet_out(db: Session, team: Team) -> dict:
    types = list(db.scalars(select(PriceType).where(PriceType.is_active).order_by(PriceType.sort_order, PriceType.name)))
    chosen = set(db.scalars(select(TeamPriceType.price_type_code).where(TeamPriceType.team_id == team.id)))
    own = {(p.product_id, p.price_type_code): p.amount_centavos for p in db.scalars(select(TeamPrice).where(TeamPrice.team_id == team.id))}
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
                    code: {"company": company.get(code), "team": own.get((p.id, code))}
                    for code in listed
                    for company in [{x.price_type_code: x.amount_centavos for x in p.prices}]
                },
            }
            for p in products
        ],
    }


@router.get("/teams")
def list_teams(access: SetPrices, db: DB) -> list[dict]:
    return [{"id": t.id, "name": t.name} for t in teams_for(db, access)]


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
    for n, item in enumerate(body.items):
        if item.product_id not in products or item.price_type_code not in listed:
            raise field_error(f"items.{n}", "That product or price type isn't in the price list.")
        there = db.get(TeamPrice, (found.id, item.product_id, item.price_type_code))
        if item.amount_centavos is None:
            if there:
                db.delete(there)
        elif there:
            there.amount_centavos = item.amount_centavos
        else:
            db.add(TeamPrice(team_id=found.id, product_id=item.product_id, price_type_code=item.price_type_code, amount_centavos=item.amount_centavos))
    if body.items:
        audit(db, me, "team_prices.set", target=found.name, target_type="team", target_id=found.id)
        db.commit()
    return sheet_out(db, found)
