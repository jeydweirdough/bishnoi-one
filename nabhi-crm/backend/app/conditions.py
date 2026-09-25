"""Price rules: how a quote line is priced, in an order an admin sets
(benchmarks/decisions.md, D4; SAP's condition technique).

A line's price comes in two parts, then tax:

1. **Its price**, from the first source in the procedure's `price` list that
   has one: a customer-group price, the team's own price, or the list price
   (always there as the last resort).
2. **Adjustments**, in the procedure's `adjust` order, each on what the line
   comes to so far: a volume scale, the promo the rep picked, the rep's own
   discount, a surcharge. One left out of the list is switched off.
3. **Tax**, from Finance, when the procedure says so (app/finance.py).

Every condition is dated and can be switched off. When several could apply
to a line, the most specific wins: this product and this group, then this
product for everyone, then every product for this group, then every product
for everyone; among equals, the one that started latest.
"""

from dataclasses import dataclass, field

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PriceCondition, SalesSettings

PRICE_SOURCES: dict[str, str] = {
    "group_price": "Customer-group price",
    "team_price": "Team price",
    "list_price": "List price",
}
ADJUSTMENTS: dict[str, str] = {
    "volume": "Volume scale",
    "promo": "Promo",
    "manual": "Rep's discount",
    "surcharge": "Surcharge",
}
DEFAULT_PROCEDURE: dict = {
    "price": ["group_price", "team_price", "list_price"],
    "adjust": ["volume", "promo", "manual", "surcharge"],
    "tax": False,
}


def procedure_of(settings: SalesSettings) -> dict:
    """The procedure in force: the admin's, or the default until they set one."""
    saved = settings.pricing_procedure or {}
    return {
        "price": saved.get("price") or list(DEFAULT_PROCEDURE["price"]),
        "adjust": saved["adjust"] if "adjust" in saved else list(DEFAULT_PROCEDURE["adjust"]),
        "tax": bool(saved.get("tax", DEFAULT_PROCEDURE["tax"])),
    }


def check_procedure(price: list[str], adjust: list[str]) -> None:
    """Raises a field error for an order that can't work."""

    def bad(field: str, message: str) -> HTTPException:
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", field], "msg": message}])

    if len(set(price)) != len(price) or not set(price) <= set(PRICE_SOURCES):
        raise bad("price", "List each price source once.")
    if "list_price" not in price:
        raise bad("price", "Keep the list price: it's where a price comes from when nothing else has one.")
    if len(set(adjust)) != len(adjust) or not set(adjust) <= set(ADJUSTMENTS):
        raise bad("adjust", "List each adjustment once.")


def running(c: PriceCondition, on: str) -> bool:
    return c.is_active and (c.starts_on is None or c.starts_on <= on) and (c.ends_on is None or on <= c.ends_on)


def specificity(c: PriceCondition) -> tuple[int, str]:
    """Higher wins: product (2) and group (1) named, then the latest start."""
    return (2 if c.product_id else 0) + (1 if c.price_group_code else 0), c.starts_on or ""


@dataclass
class Conditions:
    """The conditions running on one day, ready to match lines against."""

    group_prices: list[PriceCondition] = field(default_factory=list)
    volumes: list[PriceCondition] = field(default_factory=list)
    surcharges: list[PriceCondition] = field(default_factory=list)

    def group_price(self, product_id: str, group: str | None, price_type: str) -> PriceCondition | None:
        """This group's price for this product, at this price type (a price set
        for one price type beats one set for every type)."""
        if not group:
            return None
        found = [
            c for c in self.group_prices
            if c.product_id == product_id and c.price_group_code == group and c.price_type_code in (price_type, None)
        ]
        return max(found, key=lambda c: (c.price_type_code is not None, c.starts_on or ""), default=None)

    @staticmethod
    def _best(conditions: list[PriceCondition], product_id: str, group: str | None) -> PriceCondition | None:
        matching = [
            c for c in conditions
            if c.product_id in (None, product_id) and (c.price_group_code is None or c.price_group_code == group)
        ]
        return max(matching, key=specificity, default=None)

    def volume(self, product_id: str, group: str | None) -> PriceCondition | None:
        return self._best(self.volumes, product_id, group)

    def surcharge(self, product_id: str, group: str | None) -> PriceCondition | None:
        return self._best(self.surcharges, product_id, group)


def load(db: Session, on: str) -> Conditions:
    found = Conditions()
    for c in db.scalars(select(PriceCondition)):
        if not running(c, on):
            continue
        {"group_price": found.group_prices, "volume": found.volumes, "surcharge": found.surcharges}[c.kind].append(c)
    return found


def volume_bp(c: PriceCondition, quantity: int) -> int:
    """The best tier the quantity reaches."""
    reached = [t["percentBp"] for t in c.tiers or [] if quantity >= t["minQty"]]
    return max(reached, default=0)
