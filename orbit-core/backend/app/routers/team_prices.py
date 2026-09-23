"""Prices: what one team charges.

The company's price list (Settings -> Pricing, Inventory) is the default and
stays exactly as it is. A team's lead may set their team's own amount for any
product, and narrow the price types their team quotes with. Anything they leave
alone follows the company, so a team that sets nothing prices as it always did.

There is deliberately no floor and no approval: the owners decided the lead's
number is the number. Every change lands in the audit log instead.
"""

from fastapi import APIRouter, status
from sqlalchemy import select

from app.audit import audit
from app.errors import field_errors
from app.models import Product, ProductPrice, TeamPrice, TeamPriceType
from app.price_book import load_price_types, load_rules, load_team_prices, team_price_types
from app.routers.sales import WS, Workspace
from app.schemas import TeamPriceTypesIn, TeamPricesIn
from app.scope import Scope

# A sheet belongs to one team, and a team to one division, so both are named
# rather than taken from the address: the workspace spans every division its
# person sells in (app/routers/sales.py).
router = APIRouter(prefix="/sales/prices", tags=["prices"])


def prices_out(ws: Workspace, scope: Scope) -> dict:
    """The team's price sheet: every active product, the company's price beside
    the team's own, and which price types the team quotes with."""
    division, team = scope.division, scope.subdivision
    division_rules = load_rules(ws.db, division)
    chosen = team_price_types(ws.db, division, team)
    types = load_price_types(ws.db)
    theirs = load_team_prices(ws.db, division, team)
    products = ws.db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.name))
    company = {
        (row.product_id, row.price_type_code): row.amount_centavos for row in ws.db.scalars(select(ProductPrice))
    }
    return {
        "division": division,
        "divisionName": ws.division_name(scope),
        "team": team,
        "teamName": ws.team_name(scope),
        "usesDivisionTypes": not chosen,
        "priceTypes": [
            {
                "code": code,
                "name": types[code].name,
                "entry": types[code].entry,
                "rule": rule,
                "chosen": code in chosen if chosen else True,
            }
            for code, rule in division_rules.price_types.items()
            if code in types
        ],
        "products": [
            {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "unit": p.unit,
                "prices": {
                    code: {
                        "company": company.get((p.id, code)),
                        "team": theirs.get((p.id, code)),
                    }
                    for code in division_rules.price_types
                    if code in types and types[code].entry == "list"
                },
            }
            for p in products
        ],
    }


def their_team(ws: Workspace, division: str, team: str) -> Scope:
    """The scope they may set prices for. A Team Lead has their own teams; a
    Division Head has every team in the division."""
    scope = ws.active_team(division, team)
    ws.require("prices", scope)
    return scope


@router.get("/teams")
def priceable_teams(ws: WS) -> list[dict]:
    """Every team this person sets prices for, in any division they sell in.
    One list, because which division a team is in is something the team says,
    not somewhere its lead has to go first."""
    return sorted(
        (
            {
                "division": scope.division,
                "divisionName": ws.division_name(scope),
                "team": scope.subdivision,
                "teamName": ws.team_name(scope),
            }
            for scope in ws.scopes("prices")
        ),
        key=lambda t: (t["divisionName"].casefold(), t["teamName"].casefold()),
    )


@router.get("")
def team_prices(ws: WS, division: str, team: str) -> dict:
    return prices_out(ws, their_team(ws, division, team))


@router.put("")
def set_team_prices(ws: WS, division: str, team: str, body: TeamPricesIn) -> dict:
    """Sets or clears this team's own prices. An item with no amount hands that
    price back to the company's."""
    scope = their_team(ws, division, team)
    types = load_rules(ws.db, division).price_types
    known_products = set(ws.db.scalars(select(Product.id)))
    errors: list[tuple[tuple, str]] = []
    for i, item in enumerate(body.items):
        if item.product_id not in known_products:
            errors.append((("items", i, "productId"), "That product is gone. Reload and try again."))
        if item.price_type_code not in types:
            errors.append((("items", i, "priceTypeCode"), "Your division doesn't quote with that price type."))
    if errors:
        raise field_errors(errors)

    existing = {
        (row.product_id, row.price_type_code): row
        for row in ws.db.scalars(
            select(TeamPrice).where(TeamPrice.division_code == division, TeamPrice.subdivision_code == team)
        )
    }
    changed = 0
    for item in body.items:
        key = (item.product_id, item.price_type_code)
        row = existing.get(key)
        if item.amount_centavos is None:
            if row is not None:
                ws.db.delete(row)
                changed += 1
            continue
        if row is None:
            ws.db.add(
                TeamPrice(
                    division_code=division,
                    subdivision_code=team,
                    product_id=item.product_id,
                    price_type_code=item.price_type_code,
                    amount_centavos=item.amount_centavos,
                    set_by_id=ws.user.id,
                )
            )
            changed += 1
        elif row.amount_centavos != item.amount_centavos:
            row.amount_centavos, row.set_by_id = item.amount_centavos, ws.user.id
            changed += 1
    ws.db.commit()
    if changed:
        audit(ws.db, ws.user, "team_prices.changed", scope.key, {"prices": changed})
    return prices_out(ws, scope)


@router.put("/types", status_code=status.HTTP_200_OK)
def set_team_price_types(ws: WS, division: str, team: str, body: TeamPriceTypesIn) -> dict:
    """Which price types this team quotes with. Sending every one of the
    division's, or none at all, means "follow the division"."""
    scope = their_team(ws, division, team)
    allowed = set(load_rules(ws.db, division).price_types)
    unknown = [c for c in body.codes if c not in allowed]
    if unknown:
        raise field_errors([(("codes",), "Your division doesn't quote with one of those price types.")])

    ws.db.execute(
        TeamPriceType.__table__.delete().where(
            TeamPriceType.division_code == division, TeamPriceType.subdivision_code == team
        )
    )
    # Every one of them is the same as choosing none: the team simply follows.
    if body.codes and set(body.codes) != allowed:
        for code in body.codes:
            ws.db.add(
                TeamPriceType(
                    division_code=division, subdivision_code=team, price_type_code=code, set_by_id=ws.user.id
                )
            )
    ws.db.commit()
    audit(ws.db, ws.user, "team_price_types.changed", scope.key, {"codes": len(body.codes)})
    return prices_out(ws, scope)
