"""Packs that can be broken (owner's Step 4A, 2026-11-18): quantities and sales in an item's packs.

Stock is always kept in the item's base unit. An item's packs (step 14e: Box = 10 strips) say how many base
units each holds; this module writes a base quantity in packs ("2 Boxes + 4 Strips"), says how a sale line
was sold ("2 Boxes of 10") and what a pack sells for (its own price, or the base price x quantity).
"""

from modules.inventory.models import Packaging, Product


def plural(name: str, n: int) -> str:
    """Box → Boxes, Strip → Strips, tablet → tablets; one stays as it is."""
    if n == 1 or not name:
        return name
    low = name.lower()
    if low.endswith(("s", "x", "z", "ch", "sh")):
        return name + "es"
    if low.endswith("y") and len(low) > 1 and low[-2] not in "aeiou":
        return name[:-1] + "ies"
    return name + "s"


def counted(n: int, name: str) -> str:
    return f"{n:,} {plural(name, n)}"


def in_packs(quantity: int, packs: list[dict], unit: str) -> str | None:
    """A base quantity in packs, largest first, the rest in smaller packs or the base unit: 1,050 tablets with
    Box = 100 and Strip = 10 → "10 Boxes + 5 Strips". None when the item has no packs or nothing is there."""
    if not packs or quantity <= 0:
        return None
    left, parts = quantity, []
    for p in sorted(packs, key=lambda p: -int(p["quantity"])):
        n = left // int(p["quantity"])
        if n > 0:
            parts.append(counted(n, p["name"]))
            left -= n * int(p["quantity"])
    if not parts:
        return None
    if left > 0:
        parts.append(counted(left, unit))
    return " + ".join(parts)


def sold_as(quantity: int, unit_name: str | None, per: int | None) -> str | None:
    """How a line was sold: 20 tablets as Boxes of 10 → "2 Boxes of 10". None for the base unit."""
    per = per or 1
    if not unit_name or per <= 1 or quantity % per:
        return None
    return f"{counted(quantity // per, unit_name)} of {per:,}"


def pack_price(product: Product, pack: Packaging) -> int:
    """What one pack sells for, in centavos."""
    return pack.price if pack.price is not None else product.selling_price * pack.quantity


def largest(packs: list[dict]) -> int | None:
    return max((int(p["quantity"]) for p in packs), default=None)
