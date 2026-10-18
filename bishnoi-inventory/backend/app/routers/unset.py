"""What isn't set up yet, for the sidebar's red counts.

Each count is a thing somebody has to fill in before Inventory works in full: a
product with no selling price sells for nothing, one with no cost is valued at
nothing. Only the counts this person may fix are sent, so a mark in their
sidebar is always one they can act on.
"""

from fastapi import APIRouter
from sqlalchemy import func, select

from app.access import CurrentAccess
from app.deps import DB
from app.models import Product, Receipt, Stock, Supplier, Warehouse
from app.routers.catalog import missing_a_price

router = APIRouter(prefix="/inventory", tags=["unset"])


@router.get("/unset")
def unset(access: CurrentAccess, db: DB) -> dict[str, int]:
    """How many of each thing isn't set yet, by kind. Kinds are left out when
    this person can't fix them, and when nothing is missing."""
    counts: dict[str, int] = {}
    if access.can("products.edit"):
        counts["productPrices"] = db.scalar(select(func.count()).select_from(Product).where(missing_a_price())) or 0
    return {k: v for k, v in counts.items() if v}


@router.get("/setup")
def setup(_: CurrentAccess, db: DB) -> dict[str, int]:
    """What exists so far, for the order Inventory is set up in: warehouses and
    suppliers, then products and their prices, then stock received into them.
    The home page's guide and each New page's "needs first" read it."""
    physical = Product.product_type != "service"
    return {
        "warehouses": db.scalar(select(func.count()).select_from(Warehouse).where(Warehouse.is_active)) or 0,
        "suppliers": db.scalar(select(func.count()).select_from(Supplier).where(Supplier.is_active)) or 0,
        "products": db.scalar(select(func.count()).select_from(Product).where(physical, Product.status == "active")) or 0,
        "unpriced": db.scalar(select(func.count()).select_from(Product).where(missing_a_price())) or 0,
        "stocked": db.scalar(select(func.count(func.distinct(Stock.product_id))).where(Stock.on_hand > 0)) or 0,
        "receipts": db.scalar(select(func.count()).select_from(Receipt)) or 0,
    }
