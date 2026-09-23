"""Turning a bundle on a quote into priced lines.

Pure, like app/pricing.py: no database and no I/O, so the sharing maths can be
tested on its own. app/price_book.py loads what this needs.

A bundle is a set of products at one price. What the customer reads depends on
the bundle's own switch:

- **one line** — "Starter Pack, 1 set, P1,800", with its contents named
  underneath. The products are still known, so Dispatch packs the right box and
  stock still moves per product.
- **its items** — a line per product, with the set's price shared across them in
  proportion to what each lists at. The dearer item carries more of the
  discount, which is what anyone would get doing it by hand.

Either way the lines add up to the set price exactly. The share is worked out in
whole centavos and the last line takes the remainder, because thirds of P1,000
don't divide and Finance reconciles these to the centavo.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # app.pricing imports this module, so the arrow only points one way.
    from app.pricing import ProductInfo


@dataclass(frozen=True)
class BundleItemInfo:
    product_id: str
    qty: int


@dataclass(frozen=True)
class BundleInfo:
    id: str
    code: str
    name: str
    price_centavos: int
    as_one_line: bool
    items: tuple[BundleItemInfo, ...]


class BundleError(ValueError):
    """Worded for the rep: why this bundle can't go on this quote."""


def share_price(
    bundle: BundleInfo,
    sets: int,
    products: dict[str, "ProductInfo"],
    price_type_code: str,
    price_type_name: str,
) -> list[tuple[str, int, int]]:
    """(product id, units, centavos) per item, adding up to the set price exactly.

    Split in proportion to what each item lists at in this quote's price type.
    Every item must have a price there: a bundle can't be shared out against
    prices that don't exist, and quietly charging zero for one item would be
    worse than refusing.
    """
    if not bundle.items:
        raise BundleError(f"{bundle.name} has no products in it yet.")

    lists_at: list[int] = []
    for item in bundle.items:
        product = products.get(item.product_id)
        if product is None or not product.is_active:
            raise BundleError(f"{bundle.name} contains a product that is no longer sold.")
        unit_price = product.prices.get(price_type_code)
        if unit_price is None:
            raise BundleError(f"{product.name}, in {bundle.name}, has no {price_type_name} yet. Ask Inventory to add it.")
        lists_at.append(unit_price * item.qty * sets)

    total_list = sum(lists_at)
    set_price = bundle.price_centavos * sets
    if total_list <= 0:
        # Everything in it is priced at zero, so there is nothing to share out by.
        raise BundleError(f"The products in {bundle.name} have no {price_type_name} to share its price across.")

    shares: list[int] = []
    for value in lists_at[:-1]:
        # Rounded half up, like every other amount in the pricing engine.
        shares.append((set_price * value + total_list // 2) // total_list)
    shares.append(set_price - sum(shares))  # the last line takes the remainder

    return [(item.product_id, item.qty * sets, amount) for item, amount in zip(bundle.items, shares, strict=True)]


def contents(bundle: BundleInfo, products: dict[str, "ProductInfo"]) -> str:
    """"2 x Amoxicillin 500mg, 1 x Paracetamol 500mg" — what a one-line bundle
    prints underneath itself, so nobody has to open it to know what is in it."""
    parts = []
    for item in bundle.items:
        product = products.get(item.product_id)
        parts.append(f"{item.qty} × {product.name if product else 'a product no longer sold'}")
    return ", ".join(parts)
