"""The catalogue: products (with their variants, specifications, pictures and
supplier prices), categories, brands and units of measure.

    Medical Supplies → Syringes → BD Syringe → 1 mL, 3 mL, 5 mL
    (category)         (category)  (product)    (variants)
"""

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.access import allowed
from app.api import Api, changed, conflict, field_error, found, iso, not_found
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.levels import ZERO, by_product, by_warehouse, state, suggested_order
from app.models import (
    PRODUCT_STATUSES,
    PRODUCT_TYPES,
    Batch,
    Brand,
    Category,
    Location,
    Movement,
    Product,
    ProductImage,
    Stock,
    Supplier,
    SupplierProduct,
    Unit,
    Warehouse,
)
from app.out import batch_ref, product_ref, supplier_ref, warehouse_ref

router = APIRouter(prefix="/inventory", tags=["catalog"])

View = allowed("products.view")
Create = allowed("products.create")
Edit = allowed("products.edit")
Delete = allowed("products.delete")

IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
IMAGE_BYTES = 2 * 1024 * 1024


def category_path(c: Category | None) -> str | None:
    """Medical Supplies › Syringes."""
    names = []
    seen = set()
    while c is not None and c.id not in seen:
        seen.add(c.id)
        names.append(c.name)
        c = c.parent
    return " › ".join(reversed(names)) if names else None


# --- what every form picks from ---------------------------------------------------------


@router.get("/reference")
def reference(_: CurrentUser, db: DB) -> dict:
    """The lists forms pick from: categories, brands, units, suppliers,
    warehouses with their locations, and products."""
    categories = db.scalars(select(Category)).all()
    locations: dict[str, list[dict]] = {}
    for loc in db.scalars(select(Location).order_by(Location.is_default.desc(), Location.code)):
        locations.setdefault(loc.warehouse_id, []).append({"id": loc.id, "code": loc.code, "name": loc.name, "isDefault": loc.is_default, "isActive": loc.is_active})
    products = db.scalars(select(Product).where(Product.product_type != "service").order_by(func.lower(Product.name)))
    return {
        "categories": sorted(
            ({"id": c.id, "name": c.name, "path": category_path(c), "parentId": c.parent_id, "isActive": c.is_active} for c in categories),
            key=lambda c: c["path"].lower(),
        ),
        "brands": [{"id": b.id, "name": b.name, "isActive": b.is_active} for b in db.scalars(select(Brand).order_by(func.lower(Brand.name)))],
        "units": [{"code": u.code, "name": u.name, "isActive": u.is_active} for u in db.scalars(select(Unit).order_by(Unit.name))],
        "suppliers": [
            {**supplier_ref(s), "isActive": s.is_active} for s in db.scalars(select(Supplier).order_by(func.lower(Supplier.name)))
        ],
        "warehouses": [
            {**warehouse_ref(w), "isActive": w.is_active, "locations": locations.get(w.id, [])}
            for w in db.scalars(select(Warehouse).order_by(Warehouse.code))
        ],
        "products": [
            {**product_ref(p), "status": p.status, "costPrice": p.cost_price, "sellingPrice": p.selling_price, "supplierId": p.supplier_id}
            for p in products
        ],
    }


# --- categories -------------------------------------------------------------------------


class CategoryIn(Api):
    name: str = Field(min_length=1, max_length=80)
    parent_id: str | None = Field(None, max_length=36)
    description: str | None = Field(None, max_length=300)
    is_active: bool = True


class CategoryPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    parent_id: str | None = Field(None, max_length=36)
    description: str | None = Field(None, max_length=300)
    is_active: bool | None = None


def check_parent(db: DB, category: Category | None, parent_id: str | None) -> None:
    if parent_id is None:
        return
    parent = db.get(Category, parent_id)
    if parent is None:
        raise field_error("parentId", "Pick a category that exists.")
    # Walk up from the new parent: meeting this category means a loop.
    seen = parent
    while seen is not None:
        if category is not None and seen.id == category.id:
            raise field_error("parentId", "A category can't sit inside itself or one of its own.")
        seen = seen.parent


@router.get("/categories")
def list_categories(_: View, db: DB) -> list[dict]:
    counts = dict(db.execute(select(Product.category_id, func.count()).group_by(Product.category_id)).all())
    children = dict(db.execute(select(Category.parent_id, func.count()).where(Category.parent_id.is_not(None)).group_by(Category.parent_id)).all())
    rows = [
        {
            "id": c.id,
            "name": c.name,
            "path": category_path(c),
            "parentId": c.parent_id,
            "description": c.description,
            "isActive": c.is_active,
            "productCount": counts.get(c.id, 0),
            "childCount": children.get(c.id, 0),
        }
        for c in db.scalars(select(Category))
    ]
    return sorted(rows, key=lambda r: r["path"].lower())


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(_: Create, me: CurrentUser, db: DB, body: CategoryIn) -> dict:
    check_parent(db, None, body.parent_id)
    category = Category(**body.model_dump())
    db.add(category)
    db.flush()
    audit(db, me, "category.created", target=category.name, target_type="category", target_id=category.id)
    db.commit()
    return {"id": category.id}


@router.patch("/categories/{category_id}")
def update_category(_: Edit, me: CurrentUser, db: DB, category_id: str, body: CategoryPatch) -> dict:
    category = found(db, Category, category_id, "category")
    wanted = changed(body)
    if "name" in wanted and not wanted["name"]:
        raise field_error("name", "Give it a name.")
    if "parent_id" in wanted:
        check_parent(db, category, wanted["parent_id"])
    fields = [k for k, v in wanted.items() if getattr(category, k) != v]
    for k in fields:
        setattr(category, k, wanted[k])
    if fields:
        audit(db, me, "category.updated", target=category.name, target_type="category", target_id=category.id, fields=fields)
        db.commit()
    return {"id": category.id}


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(_: Delete, me: CurrentUser, db: DB, category_id: str) -> Response:
    category = found(db, Category, category_id, "category")
    if db.scalar(select(func.count()).select_from(Category).where(Category.parent_id == category.id)):
        raise conflict("Other categories sit inside this one. Move or delete them first.")
    products = db.scalar(select(func.count()).select_from(Product).where(Product.category_id == category.id)) or 0
    if products:
        raise conflict(f"{products} product{'s are' if products != 1 else ' is'} in this category. Move them first, or switch it off.")
    audit(db, me, "category.deleted", target=category.name, target_type="category", target_id=category.id)
    db.delete(category)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- brands -----------------------------------------------------------------------------


class BrandIn(Api):
    name: str = Field(min_length=1, max_length=80)
    is_active: bool = True


class BrandPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    is_active: bool | None = None


def brand_taken(db: DB, name: str, but: str | None = None) -> bool:
    q = select(Brand.id).where(func.lower(Brand.name) == name.lower())
    return db.scalar(q.where(Brand.id != but) if but else q) is not None


@router.get("/brands")
def list_brands(_: View, db: DB) -> list[dict]:
    counts = dict(db.execute(select(Product.brand_id, func.count()).group_by(Product.brand_id)).all())
    return [
        {"id": b.id, "name": b.name, "isActive": b.is_active, "productCount": counts.get(b.id, 0)}
        for b in db.scalars(select(Brand).order_by(func.lower(Brand.name)))
    ]


@router.post("/brands", status_code=status.HTTP_201_CREATED)
def create_brand(_: Create, me: CurrentUser, db: DB, body: BrandIn) -> dict:
    if brand_taken(db, body.name):
        raise field_error("name", "There's already a brand with that name.")
    brand = Brand(**body.model_dump())
    db.add(brand)
    db.flush()
    audit(db, me, "brand.created", target=brand.name, target_type="brand", target_id=brand.id)
    db.commit()
    return {"id": brand.id}


@router.patch("/brands/{brand_id}")
def update_brand(_: Edit, me: CurrentUser, db: DB, brand_id: str, body: BrandPatch) -> dict:
    brand = found(db, Brand, brand_id, "brand")
    wanted = changed(body)
    if wanted.get("name") and brand_taken(db, wanted["name"], but=brand.id):
        raise field_error("name", "There's already a brand with that name.")
    fields = [k for k, v in wanted.items() if v is not None and getattr(brand, k) != v]
    for k in fields:
        setattr(brand, k, wanted[k])
    if fields:
        audit(db, me, "brand.updated", target=brand.name, target_type="brand", target_id=brand.id, fields=fields)
        db.commit()
    return {"id": brand.id}


@router.delete("/brands/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand(_: Delete, me: CurrentUser, db: DB, brand_id: str) -> Response:
    brand = found(db, Brand, brand_id, "brand")
    products = db.scalar(select(func.count()).select_from(Product).where(Product.brand_id == brand.id)) or 0
    if products:
        raise conflict(f"{products} product{'s carry' if products != 1 else ' carries'} this brand. Switch it off instead.")
    audit(db, me, "brand.deleted", target=brand.name, target_type="brand", target_id=brand.id)
    db.delete(brand)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- units of measure -------------------------------------------------------------------


class UnitIn(Api):
    code: str = Field(min_length=1, max_length=16, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=60)


class UnitPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=60)
    is_active: bool | None = None


@router.get("/units")
def list_units(_: View, db: DB) -> list[dict]:
    counts = dict(db.execute(select(Product.unit_code, func.count()).group_by(Product.unit_code)).all())
    return [{"code": u.code, "name": u.name, "isActive": u.is_active, "productCount": counts.get(u.code, 0)} for u in db.scalars(select(Unit).order_by(Unit.name))]


@router.post("/units", status_code=status.HTTP_201_CREATED)
def create_unit(_: Create, me: CurrentUser, db: DB, body: UnitIn) -> dict:
    if db.get(Unit, body.code):
        raise field_error("code", "There's already a unit with that code.")
    db.add(Unit(code=body.code, name=body.name))
    audit(db, me, "unit.created", target=body.code, target_type="unit", target_id=body.code)
    db.commit()
    return {"code": body.code}


@router.patch("/units/{code}")
def update_unit(_: Edit, me: CurrentUser, db: DB, code: str, body: UnitPatch) -> dict:
    unit = found(db, Unit, code, "unit")
    wanted = changed(body)
    fields = [k for k, v in wanted.items() if v is not None and getattr(unit, k) != v]
    for k in fields:
        setattr(unit, k, wanted[k])
    if fields:
        audit(db, me, "unit.updated", target=unit.code, target_type="unit", target_id=unit.code, fields=fields)
        db.commit()
    return {"code": unit.code}


@router.delete("/units/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit(_: Delete, me: CurrentUser, db: DB, code: str) -> Response:
    unit = found(db, Unit, code, "unit")
    if db.scalar(select(func.count()).select_from(Product).where(Product.unit_code == code)):
        raise conflict("Products are measured in this unit. Switch it off instead.")
    audit(db, me, "unit.deleted", target=unit.code, target_type="unit", target_id=unit.code)
    db.delete(unit)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- products ---------------------------------------------------------------------------


Attributes = dict[str, str]


def clean_attributes(value: dict | None) -> dict | None:
    if value is None:
        return None
    out = {}
    for k, v in value.items():
        k, v = str(k).strip(), str(v).strip()
        if k and v:
            if len(k) > 60 or len(v) > 200:
                raise ValueError("Keep a specification's name under 60 characters and its value under 200.")
            out[k] = v
    if len(out) > 40:
        raise ValueError("Keep to 40 specifications.")
    return out


class ProductFields(Api):
    name: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = Field(None, max_length=4000)
    category_id: str | None = Field(None, max_length=36)
    brand_id: str | None = Field(None, max_length=36)
    product_type: str | None = None
    unit_code: str | None = Field(None, max_length=16)
    barcode: str | None = Field(None, max_length=64)
    supplier_id: str | None = Field(None, max_length=36)
    cost_price: int | None = Field(None, ge=0, le=10**12)
    selling_price: int | None = Field(None, ge=0, le=10**12)
    tax_rate_bp: int | None = Field(None, ge=0, le=10000)
    tax_inclusive: bool | None = None
    min_stock: int | None = Field(None, ge=0, le=10**9)
    max_stock: int | None = Field(None, ge=0, le=10**9)
    reorder_point: int | None = Field(None, ge=0, le=10**9)
    reorder_qty: int | None = Field(None, ge=0, le=10**9)
    status: str | None = None
    track_batches: bool | None = None
    track_expiry: bool | None = None
    track_serials: bool | None = None
    attributes: Attributes | None = None
    parent_id: str | None = Field(None, max_length=36)
    variant_label: str | None = Field(None, max_length=80)

    _attributes = field_validator("attributes")(clean_attributes)

    @field_validator("product_type")
    @classmethod
    def _type(cls, v: str | None) -> str | None:
        if v is not None and v not in PRODUCT_TYPES:
            raise ValueError("Pick a product type.")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None and v not in PRODUCT_STATUSES:
            raise ValueError("Pick a status.")
        return v


class ProductIn(ProductFields):
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)


class ProductPatch(ProductFields):
    sku: str | None = Field(None, min_length=1, max_length=40)


def get_product(db: DB, product_id: str) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise not_found("product")
    return product


def check_product(db: DB, product: Product) -> None:
    """The rules a product's fields keep with each other, checked after they're set."""
    if product.category_id and db.get(Category, product.category_id) is None:
        raise field_error("categoryId", "Pick a category that exists.")
    if product.brand_id and db.get(Brand, product.brand_id) is None:
        raise field_error("brandId", "Pick a brand that exists.")
    if product.supplier_id and db.get(Supplier, product.supplier_id) is None:
        raise field_error("supplierId", "Pick a supplier that exists.")
    if db.get(Unit, product.unit_code) is None:
        raise field_error("unitCode", "Pick a unit of measure.")
    if product.max_stock is not None and product.max_stock < max(product.min_stock, product.reorder_point):
        raise field_error("maxStock", "The maximum can't be below the minimum or the reorder point.")
    if product.track_expiry and not product.track_batches:
        raise field_error("trackExpiry", "Expiry is kept per batch: track batches too.")
    if product.product_type == "service" and (product.track_batches or product.track_serials):
        raise field_error("productType", "A service has no stock, so nothing to track.")
    if product.barcode:
        other = db.scalar(select(Product.name).where(Product.barcode == product.barcode, Product.id != product.id))
        if other:
            raise field_error("barcode", f"{other} already has that barcode.")
    if product.parent_id:
        if product.parent_id == product.id:
            raise field_error("parentId", "A product can't be a variant of itself.")
        parent = db.get(Product, product.parent_id)
        if parent is None:
            raise field_error("parentId", "Pick a product that exists.")
        if parent.parent_id:
            raise field_error("parentId", f"{parent.name} is itself a variant. Pick the product it's a variant of.")
        if db.scalar(select(func.count()).select_from(Product).where(Product.parent_id == product.id)):
            raise field_error("parentId", "This product has variants of its own, so it can't be a variant.")


def sku_taken(db: DB, sku: str, but: str | None = None) -> bool:
    q = select(Product.id).where(func.lower(Product.sku) == sku.lower())
    return db.scalar(q.where(Product.id != but) if but else q) is not None


def product_row(p: Product, level: dict) -> dict:
    return {
        **product_ref(p),
        "barcode": p.barcode,
        "category": {"id": p.category.id, "name": p.category.name, "path": category_path(p.category)} if p.category else None,
        "brand": {"id": p.brand.id, "name": p.brand.name} if p.brand else None,
        "supplier": supplier_ref(p.supplier),
        "productType": p.product_type,
        "status": p.status,
        "costPrice": p.cost_price,
        "sellingPrice": p.selling_price,
        "reorderPoint": p.reorder_point,
        "minStock": p.min_stock,
        "maxStock": p.max_stock,
        "parentId": p.parent_id,
        "variantLabel": p.variant_label,
        "variantCount": p.variant_count,
        "level": level,
        "state": state(p, level),
        "value": level["onHand"] * p.cost_price,
    }


@router.get("/products")
def list_products(
    _: View,
    db: DB,
    q: str | None = Query(None, max_length=100),
    category: str | None = Query(None, max_length=36),
    brand: str | None = Query(None, max_length=36),
    supplier: str | None = Query(None, max_length=36),
    status_: str | None = Query(None, alias="status", max_length=16),
    stock: str | None = Query(None, max_length=8, description="low, out, over"),
    parent: str | None = Query(None, max_length=36, description="the variants of this product"),
) -> list[dict]:
    query = select(Product).order_by(func.lower(Product.name))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Product.name).like(like), func.lower(Product.sku).like(like), func.lower(Product.barcode).like(like)))
    if category:
        # The category and every one inside it.
        wanted, frontier = {category}, [category]
        while frontier:
            frontier = list(db.scalars(select(Category.id).where(Category.parent_id.in_(frontier))))
            wanted.update(frontier)
        query = query.where(Product.category_id.in_(wanted))
    if brand:
        query = query.where(Product.brand_id == brand)
    if supplier:
        query = query.where(Product.supplier_id == supplier)
    if status_ and status_ != "all":
        query = query.where(Product.status == status_)
    if parent:
        query = query.where(Product.parent_id == parent)
    products = db.scalars(query).all()
    levels = by_product(db, [p.id for p in products])
    rows = [product_row(p, levels.get(p.id, dict(ZERO))) for p in products]
    if stock:
        rows = [r for r in rows if r["state"] == stock]
    return rows


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(_: Create, me: CurrentUser, db: DB, body: ProductIn) -> dict:
    if sku_taken(db, body.sku):
        raise field_error("sku", "Another product has that SKU.")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    product = Product(**fields)
    db.add(product)
    db.flush()
    check_product(db, product)
    audit(db, me, "product.created", target=f"{product.sku} {product.name}", target_type="product", target_id=product.id)
    db.commit()
    return {"id": product.id}


@router.get("/products/{product_id}")
def read_product(_: View, db: DB, settings: SettingsDep, product_id: str) -> dict:
    p = get_product(db, product_id)
    warn = settings.expiry_warning_days
    level = by_product(db, [p.id]).get(p.id, dict(ZERO))
    warehouses = {w.id: w for w in db.scalars(select(Warehouse))}
    per_warehouse = [
        {"warehouse": warehouse_ref(warehouses[wh]), **row}
        for (pid, wh), row in by_warehouse(db, [p.id]).items()
        if wh in warehouses
    ]
    balances = db.scalars(select(Stock).where(Stock.product_id == p.id, Stock.on_hand > 0)).all()
    batches = db.scalars(select(Batch).where(Batch.product_id == p.id).order_by(Batch.expires_on.is_(None), Batch.expires_on)).all()
    on_hand_by_batch: dict[str, int] = {}
    for b in balances:
        if b.batch_id:
            on_hand_by_batch[b.batch_id] = on_hand_by_batch.get(b.batch_id, 0) + b.on_hand
    variants = db.scalars(select(Product).where(Product.parent_id == p.id).order_by(Product.variant_label, Product.name)).all()
    variant_levels = by_product(db, [v.id for v in variants])
    prices = db.scalars(select(SupplierProduct).where(SupplierProduct.product_id == p.id)).all()
    images = db.scalars(select(ProductImage.id).where(ProductImage.product_id == p.id).order_by(ProductImage.created_at)).all()
    movements = db.scalars(select(Movement).where(Movement.product_id == p.id).order_by(Movement.id.desc()).limit(15)).all()
    return {
        **product_row(p, level),
        "description": p.description,
        "unitName": p.unit.name,
        "taxRateBp": p.tax_rate_bp,
        "taxInclusive": p.tax_inclusive,
        "reorderQty": p.reorder_qty,
        "suggestedOrder": suggested_order(p, level),
        "attributes": p.attributes or {},
        "parent": {"id": p.parent.id, "sku": p.parent.sku, "name": p.parent.name} if p.parent else None,
        "createdAt": iso(p.created_at),
        "updatedAt": iso(p.updated_at),
        "warehouses": sorted(per_warehouse, key=lambda r: r["warehouse"]["code"]),
        "balances": [
            {
                "warehouse": warehouse_ref(b.location.warehouse),
                "location": {"id": b.location.id, "code": b.location.code, "name": b.location.name},
                "batch": batch_ref(b.batch, warn),
                "onHand": b.on_hand,
                "damaged": b.damaged,
            }
            for b in sorted(balances, key=lambda b: (b.location.warehouse.code, b.location.code, b.batch.expires_on.isoformat() if b.batch and b.batch.expires_on else "9"))
        ],
        "batches": [{**batch_ref(b, warn), "onHand": on_hand_by_batch.get(b.id, 0)} for b in batches],
        "variants": [product_row(v, variant_levels.get(v.id, dict(ZERO))) for v in variants],
        "supplierPrices": [
            {"supplier": supplier_ref(sp.supplier), "supplierSku": sp.supplier_sku, "price": sp.price, "leadTimeDays": sp.lead_time_days, "updatedAt": iso(sp.updated_at)}
            for sp in sorted(prices, key=lambda sp: sp.price)
        ],
        "images": list(images),
        "recentMovements": [movement_brief(m) for m in movements],
    }


def movement_brief(m: Movement) -> dict:
    return {
        "id": m.id,
        "at": iso(m.at),
        "kind": m.kind,
        "quantity": m.quantity,
        "warehouse": warehouse_ref(m.warehouse),
        "batchNo": m.batch.batch_no if m.batch else None,
        "reference": m.reference,
        "referenceType": m.reference_type,
        "referenceId": m.reference_id,
        "user": m.user_name,
    }


# Tracking can't change under stock that was kept the other way.
TRACKING = ("track_batches", "track_expiry", "track_serials", "unit_code", "product_type")


@router.patch("/products/{product_id}")
def update_product(_: Edit, me: CurrentUser, db: DB, product_id: str, body: ProductPatch) -> dict:
    product = get_product(db, product_id)
    wanted = changed(body)
    required = {"sku", "name", "product_type", "unit_code", "status", "cost_price", "selling_price", "tax_rate_bp", "tax_inclusive",
                "min_stock", "reorder_point", "reorder_qty", "track_batches", "track_expiry", "track_serials", "attributes"}
    for key in required & set(wanted):
        if wanted[key] is None:
            raise field_error(key, "This can't be empty.")
    if "sku" in wanted and sku_taken(db, wanted["sku"], but=product.id):
        raise field_error("sku", "Another product has that SKU.")
    fields = [k for k, v in wanted.items() if getattr(product, k) != v]
    if set(fields) & set(TRACKING) and db.scalar(select(func.count()).select_from(Movement).where(Movement.product_id == product.id)):
        raise conflict("Stock of this product has already moved, so how it's tracked and measured can't change. Make a new product instead.")
    for k in fields:
        setattr(product, k, wanted[k])
    if fields:
        db.flush()
        check_product(db, product)
        audit(db, me, "product.updated", target=f"{product.sku} {product.name}", target_type="product", target_id=product.id, fields=fields)
        db.commit()
    return {"id": product.id}


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(_: Delete, me: CurrentUser, db: DB, product_id: str) -> Response:
    product = get_product(db, product_id)
    if db.scalar(select(func.count()).select_from(Movement).where(Movement.product_id == product.id)):
        raise conflict("This product's stock has history, which must be kept. Mark it discontinued instead.")
    audit(db, me, "product.deleted", target=f"{product.sku} {product.name}", target_type="product", target_id=product.id)
    for variant in db.scalars(select(Product).where(Product.parent_id == product.id)):
        variant.parent_id = None
    db.delete(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("This product is on a purchase order, order or transfer. Mark it discontinued instead.") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- pictures ---------------------------------------------------------------------------


@router.post("/products/{product_id}/images", status_code=status.HTTP_201_CREATED)
async def add_image(_: Edit, me: CurrentUser, db: DB, product_id: str, file: UploadFile = File(...)) -> dict:
    product = get_product(db, product_id)
    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Use a PNG, JPEG or WebP picture.")
    data = await file.read(IMAGE_BYTES + 1)
    if len(data) > IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Keep pictures under 2 MB.")
    if db.scalar(select(func.count()).select_from(ProductImage).where(ProductImage.product_id == product.id)) >= 8:
        raise conflict("A product keeps 8 pictures at most. Remove one first.")
    image = ProductImage(product_id=product.id, content_type=file.content_type, data=data)
    db.add(image)
    db.flush()
    audit(db, me, "product.image_added", target=f"{product.sku} {product.name}", target_type="product", target_id=product.id)
    db.commit()
    return {"id": image.id}


@router.get("/products/{product_id}/images/{image_id}")
def read_image(_: View, db: DB, product_id: str, image_id: str) -> Response:
    image = db.get(ProductImage, image_id)
    if image is None or image.product_id != product_id:
        raise not_found("picture")
    return Response(image.data, media_type=image.content_type, headers={"Cache-Control": "private, max-age=3600"})


@router.delete("/products/{product_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(_: Edit, me: CurrentUser, db: DB, product_id: str, image_id: str) -> Response:
    image = db.get(ProductImage, image_id)
    if image is None or image.product_id != product_id:
        raise not_found("picture")
    product = get_product(db, product_id)
    db.delete(image)
    audit(db, me, "product.image_removed", target=f"{product.sku} {product.name}", target_type="product", target_id=product.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- what suppliers charge --------------------------------------------------------------


class SupplierPriceIn(Api):
    supplier_sku: str | None = Field(None, max_length=40)
    price: int = Field(ge=0, le=10**12)
    lead_time_days: int | None = Field(None, ge=0, le=3650)


@router.put("/products/{product_id}/suppliers/{supplier_id}")
def set_supplier_price(_: Edit, me: CurrentUser, db: DB, product_id: str, supplier_id: str, body: SupplierPriceIn) -> dict:
    product = get_product(db, product_id)
    supplier = found(db, Supplier, supplier_id, "supplier")
    row = db.get(SupplierProduct, (supplier.id, product.id))
    if row is None:
        row = SupplierProduct(supplier_id=supplier.id, product_id=product.id)
        db.add(row)
    row.supplier_sku, row.price, row.lead_time_days = body.supplier_sku, body.price, body.lead_time_days
    audit(db, me, "product.supplier_price_set", target=f"{product.sku} · {supplier.name}", target_type="product", target_id=product.id)
    db.commit()
    return {"ok": True}


@router.delete("/products/{product_id}/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_supplier_price(_: Edit, me: CurrentUser, db: DB, product_id: str, supplier_id: str) -> Response:
    row = db.get(SupplierProduct, (supplier_id, product_id))
    if row is None:
        raise not_found("supplier price")
    audit(db, me, "product.supplier_price_removed", target=f"{row.product.sku} · {row.supplier.name}", target_type="product", target_id=product_id)
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

