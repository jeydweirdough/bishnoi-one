"""Units with conversions (feature plan step 14e, 2026-10-29): each item's packaging levels.

Stock is always kept in the item's base unit (tablet, piece, bottle). A packaging says how many of it a pack
holds (Strip = 10, Box = 100); forms let people type in packs and send the base quantity, scanning a pack's
barcode counts the whole pack, and screens can show a quantity in packs ("1,050 = 10 Box + 5 Strip").

    GET    /inventory/products/{id}/packagings
    POST   /inventory/products/{id}/packagings          {name, quantity, barcode, sellable, price}
    PATCH  /inventory/products/{id}/packagings/{pid}
    DELETE /inventory/products/{id}/packagings/{pid}
"""

from fastapi import APIRouter, Response, status
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.inventory.access import allowed
from modules.inventory.api import Api, changed, field_error, found
from modules.inventory.audit import audit
from modules.inventory.deps import DB, CurrentUser
from modules.inventory.models import Packaging, Product

router = APIRouter(prefix="/inventory", tags=["packagings"])

Edit = allowed("products.edit")


def packaging_out(p: Packaging) -> dict:
    return {"id": p.id, "name": p.name, "quantity": p.quantity, "barcode": p.barcode, "sellable": p.sellable, "price": p.price}


def packagings_of(db: Session, product_ids: list[str] | None = None) -> dict[str, list[dict]]:
    """Each item's packs, biggest first."""
    q = select(Packaging).order_by(Packaging.quantity.desc())
    if product_ids is not None:
        q = q.where(Packaging.product_id.in_(product_ids))
    out: dict[str, list[dict]] = {}
    for p in db.scalars(q):
        out.setdefault(p.product_id, []).append(packaging_out(p))
    return out


def barcode_taken(db: Session, code: str, but: str | None = None) -> bool:
    low = code.lower()
    if db.scalar(select(Product.id).where(func.lower(Product.barcode) == low)):
        return True
    q = select(Packaging.id).where(func.lower(Packaging.barcode) == low)
    return db.scalar(q.where(Packaging.id != but) if but else q) is not None


class PackagingIn(Api):
    name: str = Field(min_length=1, max_length=40)
    quantity: int = Field(ge=2, le=10**7)
    barcode: str | None = Field(None, max_length=64)
    # Packs that can be broken (step 4A): may it be sold, and its own price (None = base price x quantity).
    sellable: bool = True
    price: int | None = Field(None, ge=0, le=10**12)


class PackagingPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=40)
    quantity: int | None = Field(None, ge=2, le=10**7)
    barcode: str | None = Field(None, max_length=64)
    sellable: bool | None = None
    price: int | None = Field(None, ge=0, le=10**12)


def check_price(price: int | None, quantity: int, name: str) -> None:
    """Sale lines keep their quantity in the base unit and a price per base unit (so the invoice's math stays
    as it is): a pack's price must split evenly over what it holds."""
    if price is not None and price % quantity:
        raise field_error("price", f"A {name}'s price must split evenly over its {quantity:,} units (to the centavo).")


def check(db: Session, product: Product, name: str | None, barcode: str | None, but: str | None = None) -> None:
    if name and db.scalar(select(Packaging.id).where(Packaging.product_id == product.id, func.lower(Packaging.name) == name.lower(), *( [Packaging.id != but] if but else []))):
        raise field_error("name", f"{product.name} already has a {name}.")
    if barcode and barcode_taken(db, barcode, but):
        raise field_error("barcode", "Another item or pack has that barcode.")


@router.get("/products/{product_id}/packagings")
def list_packagings(_: allowed("products.view"), db: DB, product_id: str) -> list[dict]:
    product = found(db, Product, product_id, "product")
    return packagings_of(db, [product.id]).get(product.id, [])


@router.post("/products/{product_id}/packagings", status_code=status.HTTP_201_CREATED)
def add_packaging(_: Edit, me: CurrentUser, db: DB, product_id: str, body: PackagingIn) -> list[dict]:
    product = found(db, Product, product_id, "product")
    name, barcode = body.name.strip(), (body.barcode or "").strip() or None
    check(db, product, name, barcode)
    check_price(body.price, body.quantity, name)
    db.add(Packaging(product_id=product.id, name=name, quantity=body.quantity, barcode=barcode, sellable=body.sellable, price=body.price))
    audit(db, me, "product.packaging_added", target=f"{product.name} · {name}", target_type="product", target_id=product.id)
    db.commit()
    return packagings_of(db, [product.id]).get(product.id, [])


@router.patch("/products/{product_id}/packagings/{packaging_id}")
def change_packaging(_: Edit, me: CurrentUser, db: DB, product_id: str, packaging_id: str, body: PackagingPatch) -> list[dict]:
    product = found(db, Product, product_id, "product")
    p = found(db, Packaging, packaging_id, "packaging")
    if p.product_id != product.id:
        raise field_error("packagingId", "That pack isn't this item's.")
    fields = changed(body)
    if "barcode" in fields:
        fields["barcode"] = (fields["barcode"] or "").strip() or None
    if "name" in fields and fields["name"]:
        fields["name"] = fields["name"].strip()
    check(db, product, fields.get("name"), fields.get("barcode"), but=p.id)
    check_price(fields["price"] if "price" in fields else p.price, fields.get("quantity") or p.quantity, fields.get("name") or p.name)
    for k, v in fields.items():
        if v is not None or k in ("barcode", "price"):
            setattr(p, k, v)
    audit(db, me, "product.packaging_changed", target=f"{product.name} · {p.name}", target_type="product", target_id=product.id, fields=sorted(fields))
    db.commit()
    return packagings_of(db, [product.id]).get(product.id, [])


@router.delete("/products/{product_id}/packagings/{packaging_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_packaging(_: Edit, me: CurrentUser, db: DB, product_id: str, packaging_id: str) -> Response:
    product = found(db, Product, product_id, "product")
    p = found(db, Packaging, packaging_id, "packaging")
    if p.product_id != product.id:
        raise field_error("packagingId", "That pack isn't this item's.")
    audit(db, me, "product.packaging_removed", target=f"{product.name} · {p.name}", target_type="product", target_id=product.id)
    db.delete(p)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
