"""What the other Bishnoi One apps read from here: the product list (the CRM sells
from it) and how much of each there is. Read-only, and only for an app
holding one of INTEGRATION_KEYS, sent in the X-Bishnoi-Key header.

A product that only groups its variants isn't sold itself, so it isn't
listed: its variants are.
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select

from app.api import iso
from app.deps import DB, SettingsDep
from app.levels import ZERO, by_warehouse, state
from app.models import Product, Receipt, Supplier, Warehouse

MAX_SKUS = 500


def calling_app(
    settings: SettingsDep,
    x_bishnoi_key: Annotated[str | None, Header()] = None,
    # The header's name before the rename to Bishnoi One: still taken until every app is redeployed.
    x_nabhi_key: Annotated[str | None, Header()] = None,
) -> str:
    """The name of the app whose key came with the request."""
    x_bishnoi_key = x_bishnoi_key or x_nabhi_key
    if x_bishnoi_key:
        for key in settings.integration_keys:
            name, _, secret = key.get_secret_value().partition(":")
            if hmac.compare_digest(secret.encode(), x_bishnoi_key.encode()):
                return name
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This needs a Bishnoi One app's key (X-Bishnoi-Key).")


router = APIRouter(prefix="/integration", tags=["integration"], dependencies=[Depends(calling_app)])


def sold(query):
    return query.where(Product.variant_count == 0)


@router.get("/products")
def products(db: DB) -> dict:
    """Every product that's sold, whatever its status: the caller marks the
    ones no longer active as such."""
    items = db.scalars(sold(select(Product)).order_by(Product.sku)).all()
    return {
        "items": [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "description": p.description,
                "unit": {"code": p.unit.code, "name": p.unit.name},
                "status": p.status,
                "productType": p.product_type,
                # The suggested retail price, in centavos.
                "sellingPrice": p.selling_price,
                "taxRateBp": p.tax_rate_bp,
                "taxInclusive": p.tax_inclusive,
                "category": p.category.name if p.category else None,
                "brand": p.brand.name if p.brand else None,
                "variantLabel": p.variant_label,
                "attributes": p.attributes or {},
                "updatedAt": iso(p.updated_at),
            }
            for p in items
        ]
    }


@router.get("/stock")
def stock(db: DB, skus: str = Query(..., max_length=20000, description="Comma-separated SKUs")) -> dict:
    """How much of each is available, overall and per warehouse. A SKU not
    found here is left out."""
    wanted = list(dict.fromkeys(s.strip() for s in skus.split(",") if s.strip()))[:MAX_SKUS]
    # SKUs are unique whatever their case, and the CRM keeps them in capitals.
    found = db.scalars(sold(select(Product)).where(func.upper(Product.sku).in_([s.upper() for s in wanted]))).all() if wanted else []
    levels = by_warehouse(db, [p.id for p in found])
    warehouses = db.scalars(select(Warehouse).where(Warehouse.is_active).order_by(Warehouse.name)).all()
    items = []
    for p in found:
        total = dict(ZERO)
        per = []
        for w in warehouses:
            row = levels.get((p.id, w.id))
            if row is None:
                continue
            for k, v in row.items():
                total[k] += v
            if row["onHand"] or row["inTransit"]:
                per.append({"id": w.id, "code": w.code, "name": w.name, "available": row["available"], "onHand": row["onHand"], "inTransit": row["inTransit"]})
        items.append({
            "sku": p.sku,
            # out, low, ok, over; None for a service (nothing to count).
            "state": state(p, total),
            "available": total["available"],
            "onHand": total["onHand"],
            "inTransit": total["inTransit"],
            "warehouses": per,
        })
    return {"items": items}


# --- suppliers and what they delivered: for Finance's bills (decided 2026-10-24) ---------------


def supplier_tax_out(s: Supplier) -> dict:
    return {
        "id": s.id, "code": s.code, "name": s.name, "address": s.address, "tin": s.tin,
        "vatStatus": s.vat_status, "defaultAtc": s.default_atc, "paymentTerms": s.payment_terms, "isActive": s.is_active,
    }


@router.get("/suppliers")
def suppliers(db: DB, q: str | None = Query(None, max_length=80)) -> dict:
    """Every supplier, with its tax registration: Finance makes out bills to them."""
    query = select(Supplier).order_by(Supplier.name)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(func.lower(Supplier.name).like(like) | func.lower(Supplier.code).like(like))
    return {"items": [supplier_tax_out(s) for s in db.scalars(query.limit(200))]}


@router.get("/suppliers/{supplier_id}")
def one_supplier(db: DB, supplier_id: str) -> dict:
    s = db.get(Supplier, supplier_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such supplier.")
    return supplier_tax_out(s)


@router.get("/suppliers/{supplier_id}/receipts")
def supplier_receipts(db: DB, supplier_id: str) -> dict:
    """The deliveries received from a supplier, newest first, each with what came at what cost: a bill starts from one."""
    rows = db.scalars(select(Receipt).where(Receipt.supplier_id == supplier_id).order_by(Receipt.received_at.desc()).limit(50)).all()
    return {
        "items": [
            {
                "id": r.id, "number": r.number, "receivedAt": iso(r.received_at), "deliveryRef": r.delivery_ref,
                "order": r.order.number if r.order else None,
                "lines": [
                    {"product": ln.product.name, "sku": ln.product.sku, "quantity": ln.quantity, "unitCost": ln.unit_cost, "amount": ln.quantity * ln.unit_cost}
                    for ln in r.lines
                ],
                "totalCost": sum(ln.quantity * ln.unit_cost for ln in r.lines),
            }
            for r in rows
        ]
    }
