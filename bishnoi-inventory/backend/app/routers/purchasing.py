"""Buying stock in: suppliers, purchase orders, and receiving.

    Purchase order → supplier delivers → receiving → stock

A purchase order starts as a draft, is placed (ordered), and fills up as
deliveries are received against it: partial, then received. Whatever is
still owed on a placed order is a backorder. A delivery can also be received
without an order.
"""

from datetime import date

from fastapi import APIRouter, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.access import allowed
from app.api import Api, changed, check_email, conflict, field_error, found, iso
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.models import Product, PurchaseOrder, PurchaseOrderLine, Receipt, ReceiptLine, Supplier, SupplierProduct, Warehouse
from app.out import batch_ref, day, location_ref, person, product_ref, supplier_ref, today, warehouse_ref
from app.stock import Ref, clean_serials, location_in, next_number, post, resolve_batch, serials_in

router = APIRouter(prefix="/inventory", tags=["purchasing"])


# --- suppliers --------------------------------------------------------------------------


class ContactIn(Api):
    name: str = Field(min_length=1, max_length=120)
    role: str | None = Field(None, max_length=80)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=40)

    _email = field_validator("email")(check_email)


class SupplierFields(Api):
    name: str | None = Field(None, min_length=1, max_length=160)
    contact_person: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=40)
    address: str | None = Field(None, max_length=300)
    contacts: list[ContactIn] | None = Field(None, max_length=20)
    payment_terms: str | None = Field(None, max_length=80)
    lead_time_days: int | None = Field(None, ge=0, le=3650)
    notes: str | None = Field(None, max_length=4000)
    is_active: bool | None = None

    _email = field_validator("email")(check_email)


class SupplierIn(SupplierFields):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=160)


class SupplierPatch(SupplierFields):
    code: str | None = Field(None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def supplier_code_taken(db: DB, code: str, but: str | None = None) -> bool:
    q = select(Supplier.id).where(func.lower(Supplier.code) == code.lower())
    return db.scalar(q.where(Supplier.id != but) if but else q) is not None


def performance(db: DB, supplier_ids: list[str] | None = None) -> dict[str, dict]:
    """Per supplier: orders placed, what share of units came, how many came
    on time, and how long deliveries took."""
    q = select(PurchaseOrder).where(PurchaseOrder.status.in_(("ordered", "partial", "received")))
    if supplier_ids is not None:
        q = q.where(PurchaseOrder.supplier_id.in_(supplier_ids))
    out: dict[str, dict] = {}
    for po in db.scalars(q):
        row = out.setdefault(po.supplier_id, {"orders": 0, "ordered": 0, "received": 0, "spend": 0, "onTime": 0, "late": 0, "leadDays": []})
        row["orders"] += 1
        row["ordered"] += sum(line.quantity for line in po.lines)
        row["received"] += sum(line.received for line in po.lines)
        row["spend"] += sum(line.received * line.unit_cost for line in po.lines)
        first = db.scalar(select(func.min(Receipt.received_at)).where(Receipt.order_id == po.id))
        if first is not None:
            arrived = first.date()
            if po.ordered_on:
                row["leadDays"].append((arrived - po.ordered_on).days)
            if po.expected_on:
                row["onTime" if arrived <= po.expected_on else "late"] += 1
    for row in out.values():
        lead = row.pop("leadDays")
        row["averageLeadDays"] = round(sum(lead) / len(lead), 1) if lead else None
        row["fillRate"] = round(row["received"] / row["ordered"], 3) if row["ordered"] else None
        judged = row["onTime"] + row["late"]
        row["onTimeRate"] = round(row["onTime"] / judged, 3) if judged else None
    return out


def supplier_out(s: Supplier, perf: dict | None = None) -> dict:
    return {
        **supplier_ref(s),
        "contactPerson": s.contact_person,
        "email": s.email,
        "phone": s.phone,
        "address": s.address,
        "contacts": s.contacts or [],
        "paymentTerms": s.payment_terms,
        "leadTimeDays": s.lead_time_days,
        "notes": s.notes,
        "isActive": s.is_active,
        "performance": perf,
    }


@router.get("/suppliers")
def list_suppliers(_: allowed("suppliers.view"), db: DB, q: str | None = Query(None, max_length=100), state: str | None = Query(None, max_length=8)) -> list[dict]:
    query = select(Supplier).order_by(Supplier.is_active.desc(), func.lower(Supplier.name))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Supplier.name).like(like), func.lower(Supplier.code).like(like), func.lower(Supplier.contact_person).like(like)))
    if state in ("active", "off"):
        query = query.where(Supplier.is_active.is_(state == "active"))
    suppliers = db.scalars(query).all()
    perf = performance(db, [s.id for s in suppliers])
    return [supplier_out(s, perf.get(s.id)) for s in suppliers]


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(_: allowed("suppliers.create"), me: CurrentUser, db: DB, body: SupplierIn) -> dict:
    if supplier_code_taken(db, body.code):
        raise field_error("code", "Another supplier has that code.")
    data = body.model_dump(exclude_none=True)
    data["code"] = data["code"].upper()
    supplier = Supplier(**data)
    db.add(supplier)
    db.flush()
    audit(db, me, "supplier.created", target=supplier.name, target_type="supplier", target_id=supplier.id)
    db.commit()
    return {"id": supplier.id}


@router.get("/suppliers/{supplier_id}")
def read_supplier(_: allowed("suppliers.view"), db: DB, supplier_id: str) -> dict:
    s = found(db, Supplier, supplier_id, "supplier")
    prices = db.scalars(select(SupplierProduct).where(SupplierProduct.supplier_id == s.id)).all()
    supplied = db.scalars(select(Product).where(Product.supplier_id == s.id).order_by(Product.name)).all()
    orders = db.scalars(select(PurchaseOrder).where(PurchaseOrder.supplier_id == s.id).order_by(PurchaseOrder.created_at.desc()).limit(25)).all()
    return {
        **supplier_out(s, performance(db, [s.id]).get(s.id)),
        "createdAt": iso(s.created_at),
        "prices": [
            {"product": product_ref(sp.product), "supplierSku": sp.supplier_sku, "price": sp.price, "leadTimeDays": sp.lead_time_days, "updatedAt": iso(sp.updated_at)}
            for sp in sorted(prices, key=lambda sp: sp.product.name.lower())
        ],
        "products": [product_ref(p) for p in supplied],
        "orders": [po_brief(po) for po in orders],
    }


@router.patch("/suppliers/{supplier_id}")
def update_supplier(_: allowed("suppliers.edit"), me: CurrentUser, db: DB, supplier_id: str, body: SupplierPatch) -> dict:
    s = found(db, Supplier, supplier_id, "supplier")
    wanted = changed(body)
    for key in ("code", "name", "is_active"):
        if key in wanted and wanted[key] is None:
            raise field_error(key, "This can't be empty.")
    if "code" in wanted:
        wanted["code"] = wanted["code"].upper()
        if supplier_code_taken(db, wanted["code"], but=s.id):
            raise field_error("code", "Another supplier has that code.")
    if "contacts" in wanted:
        wanted["contacts"] = wanted["contacts"] or []
    fields = [k for k, v in wanted.items() if getattr(s, k) != v]
    for k in fields:
        setattr(s, k, wanted[k])
    if fields:
        audit(db, me, "supplier.updated", target=s.name, target_type="supplier", target_id=s.id, fields=fields)
        db.commit()
    return {"id": s.id}


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(_: allowed("suppliers.delete"), me: CurrentUser, db: DB, supplier_id: str) -> Response:
    s = found(db, Supplier, supplier_id, "supplier")
    if db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.supplier_id == s.id)):
        raise conflict("This supplier has purchase orders, which must be kept. Switch it off instead.")
    audit(db, me, "supplier.deleted", target=s.name, target_type="supplier", target_id=s.id)
    db.delete(s)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("This supplier is still in use. Switch it off instead.") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- purchase orders --------------------------------------------------------------------


class POLineIn(Api):
    product_id: str = Field(max_length=36)
    quantity: int = Field(gt=0, le=10**9)
    unit_cost: int = Field(ge=0, le=10**12)


class POIn(Api):
    supplier_id: str = Field(max_length=36)
    warehouse_id: str = Field(max_length=36)
    expected_on: date | None = None
    notes: str | None = Field(None, max_length=4000)
    lines: list[POLineIn] = Field(min_length=1, max_length=200)


def po_brief(po: PurchaseOrder) -> dict:
    ordered = sum(line.quantity for line in po.lines)
    received = sum(line.received for line in po.lines)
    return {
        "id": po.id,
        "number": po.number,
        "status": po.status,
        "supplier": supplier_ref(po.supplier),
        "warehouse": warehouse_ref(po.warehouse),
        "orderedOn": day(po.ordered_on),
        "expectedOn": day(po.expected_on),
        "late": po.status in ("ordered", "partial") and po.expected_on is not None and po.expected_on < today(),
        "lineCount": len(po.lines),
        "ordered": ordered,
        "received": received,
        "total": sum(line.quantity * line.unit_cost for line in po.lines),
        "createdAt": iso(po.created_at),
    }


def po_out(db: DB, po: PurchaseOrder) -> dict:
    receipts = db.scalars(select(Receipt).where(Receipt.order_id == po.id).order_by(Receipt.received_at)).all()
    return {
        **po_brief(po),
        "notes": po.notes,
        "createdBy": person(po.created_by),
        "orderedBy": person(po.ordered_by),
        "lines": [
            {
                "id": line.id,
                "product": product_ref(line.product),
                "quantity": line.quantity,
                "received": line.received,
                "outstanding": max(0, line.quantity - line.received) if po.status in ("ordered", "partial") else 0,
                "unitCost": line.unit_cost,
                "total": line.quantity * line.unit_cost,
            }
            for line in po.lines
        ],
        "receipts": [receipt_brief(r) for r in receipts],
    }


def check_po(db: DB, body: POIn) -> None:
    supplier = db.get(Supplier, body.supplier_id)
    if supplier is None or not supplier.is_active:
        raise field_error("supplierId", "Pick a supplier that's switched on.")
    warehouse = db.get(Warehouse, body.warehouse_id)
    if warehouse is None or not warehouse.is_active:
        raise field_error("warehouseId", "Pick a warehouse that's switched on.")
    seen = set()
    for i, line in enumerate(body.lines):
        product = db.get(Product, line.product_id)
        if product is None or product.product_type == "service":
            raise field_error(f"lines.{i}.productId", "Pick a stocked product.")
        if product.status == "discontinued":
            raise field_error(f"lines.{i}.productId", f"{product.name} is discontinued.")
        if line.product_id in seen:
            raise field_error(f"lines.{i}.productId", f"{product.name} is on the order twice. Put it on one line.")
        seen.add(line.product_id)


def set_lines(po: PurchaseOrder, body: POIn) -> None:
    po.lines = [PurchaseOrderLine(position=i, product_id=line.product_id, quantity=line.quantity, unit_cost=line.unit_cost) for i, line in enumerate(body.lines)]


@router.get("/purchase-orders")
def list_pos(
    _: allowed("purchasing.view"),
    db: DB,
    status_: str | None = Query(None, alias="status", max_length=40, description="a status, or several: ordered,partial"),
    supplier: str | None = Query(None, max_length=36),
    q: str | None = Query(None, max_length=60),
) -> list[dict]:
    query = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).limit(500)
    if status_:
        query = query.where(PurchaseOrder.status.in_(status_.split(",")))
    if supplier:
        query = query.where(PurchaseOrder.supplier_id == supplier)
    if q:
        query = query.join(Supplier).where(or_(func.lower(PurchaseOrder.number).like(f"%{q.lower()}%"), func.lower(Supplier.name).like(f"%{q.lower()}%")))
    return [po_brief(po) for po in db.scalars(query)]


@router.post("/purchase-orders", status_code=status.HTTP_201_CREATED)
def create_po(_: allowed("purchasing.create"), me: CurrentUser, db: DB, body: POIn) -> dict:
    check_po(db, body)
    po = PurchaseOrder(
        number=next_number(db, "PO"), supplier_id=body.supplier_id, warehouse_id=body.warehouse_id, expected_on=body.expected_on, notes=body.notes, created_by_id=me.id
    )
    set_lines(po, body)
    db.add(po)
    db.flush()
    audit(db, me, "purchase_order.created", target=po.number, target_type="purchase_order", target_id=po.id)
    db.commit()
    return {"id": po.id, "number": po.number}


@router.get("/purchase-orders/{po_id}")
def read_po(_: allowed("purchasing.view"), db: DB, po_id: str) -> dict:
    return po_out(db, found(db, PurchaseOrder, po_id, "purchase order"))


@router.put("/purchase-orders/{po_id}")
def update_po(_: allowed("purchasing.edit"), me: CurrentUser, db: DB, po_id: str, body: POIn) -> dict:
    po = found(db, PurchaseOrder, po_id, "purchase order")
    if po.status != "draft":
        raise conflict("Only a draft can be changed. This one has been placed.")
    check_po(db, body)
    po.supplier_id, po.warehouse_id, po.expected_on, po.notes = body.supplier_id, body.warehouse_id, body.expected_on, body.notes
    set_lines(po, body)
    audit(db, me, "purchase_order.updated", target=po.number, target_type="purchase_order", target_id=po.id)
    db.commit()
    return {"id": po.id}


class POExpected(Api):
    expected_on: date | None = None
    notes: str | None = Field(None, max_length=4000)


@router.patch("/purchase-orders/{po_id}")
def update_po_dates(_: allowed("purchasing.edit"), me: CurrentUser, db: DB, po_id: str, body: POExpected) -> dict:
    """What can still change on a placed order: when it's expected, and its notes."""
    po = found(db, PurchaseOrder, po_id, "purchase order")
    wanted = changed(body)
    fields = [k for k, v in wanted.items() if getattr(po, k) != v]
    for k in fields:
        setattr(po, k, wanted[k])
    if fields:
        audit(db, me, "purchase_order.updated", target=po.number, target_type="purchase_order", target_id=po.id, fields=fields)
        db.commit()
    return {"id": po.id}


@router.post("/purchase-orders/{po_id}/place")
def place_po(_: allowed("purchasing.approve"), me: CurrentUser, db: DB, po_id: str) -> dict:
    """Approves the order and sends it: from here, deliveries are received against it."""
    po = found(db, PurchaseOrder, po_id, "purchase order")
    if po.status != "draft":
        raise conflict("This order has already been placed.")
    po.status, po.ordered_on, po.ordered_by_id = "ordered", today(), me.id
    # Placing an order is when its prices become the supplier's latest.
    for line in po.lines:
        row = db.get(SupplierProduct, (po.supplier_id, line.product_id))
        if row is None:
            db.add(SupplierProduct(supplier_id=po.supplier_id, product_id=line.product_id, price=line.unit_cost))
        else:
            row.price = line.unit_cost
    audit(db, me, "purchase_order.placed", target=po.number, target_type="purchase_order", target_id=po.id)
    db.commit()
    return {"id": po.id}


@router.post("/purchase-orders/{po_id}/cancel")
def cancel_po(_: allowed("purchasing.approve"), me: CurrentUser, db: DB, po_id: str) -> dict:
    """Cancels a draft or a placed order. On a part-received one, what came
    stays; only what's still owed is let go."""
    po = found(db, PurchaseOrder, po_id, "purchase order")
    if po.status in ("received", "cancelled"):
        raise conflict(f"This order is already {po.status}.")
    po.status = "received" if po.status == "partial" else "cancelled"
    audit(db, me, "purchase_order.cancelled" if po.status == "cancelled" else "purchase_order.closed", target=po.number, target_type="purchase_order", target_id=po.id)
    db.commit()
    return {"id": po.id, "status": po.status}


@router.delete("/purchase-orders/{po_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_po(_: allowed("purchasing.edit"), me: CurrentUser, db: DB, po_id: str) -> Response:
    po = found(db, PurchaseOrder, po_id, "purchase order")
    if po.status != "draft":
        raise conflict("Only a draft can be deleted. Cancel a placed order instead.")
    audit(db, me, "purchase_order.deleted", target=po.number, target_type="purchase_order", target_id=po.id)
    db.delete(po)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/backorders")
def backorders(_: allowed("purchasing.view"), db: DB) -> list[dict]:
    """Every unit still owed on a placed order."""
    rows = db.execute(
        select(PurchaseOrderLine, PurchaseOrder)
        .join(PurchaseOrder)
        .where(PurchaseOrder.status.in_(("ordered", "partial")), PurchaseOrderLine.received < PurchaseOrderLine.quantity)
        .order_by(PurchaseOrder.expected_on.is_(None), PurchaseOrder.expected_on, PurchaseOrder.number)
    ).all()
    return [
        {
            "order": {"id": po.id, "number": po.number, "status": po.status, "expectedOn": day(po.expected_on), "late": po.expected_on is not None and po.expected_on < today()},
            "supplier": supplier_ref(po.supplier),
            "warehouse": warehouse_ref(po.warehouse),
            "product": product_ref(line.product),
            "ordered": line.quantity,
            "received": line.received,
            "outstanding": line.quantity - line.received,
            "value": (line.quantity - line.received) * line.unit_cost,
        }
        for line, po in rows
    ]


# --- receiving --------------------------------------------------------------------------


class ReceiptLineIn(Api):
    product_id: str = Field(max_length=36)
    # The purchase order's line it fills, when received against an order.
    order_line_id: str | None = Field(None, max_length=36)
    quantity: int = Field(gt=0, le=10**9)
    unit_cost: int | None = Field(None, ge=0, le=10**12)
    batch_no: str | None = Field(None, max_length=60)
    manufactured_on: date | None = None
    expires_on: date | None = None
    serials: list[str] = Field(default_factory=list, max_length=10000)


class ReceiptIn(Api):
    order_id: str | None = Field(None, max_length=36)
    supplier_id: str | None = Field(None, max_length=36)
    warehouse_id: str | None = Field(None, max_length=36)
    location_id: str | None = Field(None, max_length=36)
    delivery_ref: str | None = Field(None, max_length=60)
    notes: str | None = Field(None, max_length=4000)
    lines: list[ReceiptLineIn] = Field(min_length=1, max_length=200)


def receipt_brief(r: Receipt) -> dict:
    return {
        "id": r.id,
        "number": r.number,
        "order": {"id": r.order.id, "number": r.order.number} if r.order else None,
        "supplier": supplier_ref(r.supplier),
        "warehouse": warehouse_ref(r.warehouse),
        "location": location_ref(r.location),
        "deliveryRef": r.delivery_ref,
        "receivedAt": iso(r.received_at),
        "receivedBy": person(r.received_by),
        "units": sum(line.quantity for line in r.lines),
        "total": sum(line.quantity * line.unit_cost for line in r.lines),
    }


@router.get("/receipts")
def list_receipts(
    _: allowed("receiving.view"),
    db: DB,
    supplier: str | None = Query(None, max_length=36),
    warehouse: str | None = Query(None, max_length=36),
    q: str | None = Query(None, max_length=60),
    limit: int = Query(200, ge=1, le=1000),
) -> list[dict]:
    query = select(Receipt).order_by(Receipt.received_at.desc()).limit(limit)
    if supplier:
        query = query.where(Receipt.supplier_id == supplier)
    if warehouse:
        query = query.where(Receipt.warehouse_id == warehouse)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Receipt.number).like(like), func.lower(Receipt.delivery_ref).like(like)))
    return [receipt_brief(r) for r in db.scalars(query)]


@router.get("/receipts/{receipt_id}")
def read_receipt(_: allowed("receiving.view"), db: DB, settings: SettingsDep, receipt_id: str) -> dict:
    r = found(db, Receipt, receipt_id, "receipt")
    return {
        **receipt_brief(r),
        "notes": r.notes,
        "lines": [
            {
                "id": line.id,
                "product": product_ref(line.product),
                "quantity": line.quantity,
                "unitCost": line.unit_cost,
                "total": line.quantity * line.unit_cost,
                "batch": batch_ref(line.batch, settings.expiry_warning_days),
                "serials": line.serials or [],
            }
            for line in r.lines
        ],
    }


@router.post("/receipts", status_code=status.HTTP_201_CREATED)
def receive(_: allowed("receiving.receive"), me: CurrentUser, db: DB, body: ReceiptIn) -> dict:
    """Takes a delivery in: stock goes up, batches and serials are recorded,
    and the purchase order (if any) fills up."""
    po = None
    if body.order_id:
        po = found(db, PurchaseOrder, body.order_id, "purchase order")
        if po.status not in ("ordered", "partial"):
            raise conflict(f"{po.number} is {po.status}: only a placed order takes deliveries.")
        supplier_id, warehouse_id = po.supplier_id, body.warehouse_id or po.warehouse_id
    else:
        supplier_id, warehouse_id = body.supplier_id, body.warehouse_id
        if not warehouse_id:
            raise field_error("warehouseId", "Pick the warehouse it came into.")
        if supplier_id and db.get(Supplier, supplier_id) is None:
            raise field_error("supplierId", "Pick a supplier that exists.")
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None or not warehouse.is_active:
        raise field_error("warehouseId", "Pick a warehouse that's switched on.")
    location = location_in(db, warehouse.id, body.location_id)

    receipt = Receipt(
        number=next_number(db, "RC"),
        order_id=po.id if po else None,
        supplier_id=supplier_id,
        warehouse_id=warehouse.id,
        location_id=location.id,
        delivery_ref=body.delivery_ref,
        notes=body.notes,
        received_by_id=me.id,
    )
    db.add(receipt)
    db.flush()
    ref = Ref("receipt", receipt.id, receipt.number)
    order_lines = {line.id: line for line in po.lines} if po else {}
    for i, line in enumerate(body.lines):
        product = db.get(Product, line.product_id)
        if product is None or product.product_type == "service":
            raise field_error(f"lines.{i}.productId", "Pick a stocked product.")
        order_line = None
        if po:
            order_line = order_lines.get(line.order_line_id) if line.order_line_id else next((o for o in po.lines if o.product_id == product.id), None)
            if order_line is None or order_line.product_id != product.id:
                raise field_error(f"lines.{i}.productId", f"{product.name} isn't on {po.number}.")
            if order_line.received + line.quantity > order_line.quantity:
                owed = order_line.quantity - order_line.received
                raise field_error(f"lines.{i}.quantity", f"Only {owed} of {product.name} {'is' if owed == 1 else 'are'} still owed on {po.number}.")
            order_line.received += line.quantity
        unit_cost = line.unit_cost if line.unit_cost is not None else (order_line.unit_cost if order_line else product.cost_price)
        batch = resolve_batch(db, product, line.batch_no, manufactured_on=line.manufactured_on, expires_on=line.expires_on, supplier_id=supplier_id)
        serials = clean_serials(product, line.serials, line.quantity)
        serials_in(db, product, serials, location, batch)
        post(db, me, kind="receive", product=product, quantity=line.quantity, ref=ref, location=location, batch=batch, serials=serials, note=f"From {po.supplier.name}" if po else None)
        db.add(ReceiptLine(receipt_id=receipt.id, order_line_id=order_line.id if order_line else None, product_id=product.id, batch_id=batch.id if batch else None, quantity=line.quantity, unit_cost=unit_cost, serials=serials))
    if po:
        po.status = "received" if all(o.received >= o.quantity for o in po.lines) else "partial"
    audit(db, me, "receipt.posted", target=receipt.number + (f" · {po.number}" if po else ""), target_type="receipt", target_id=receipt.id)
    db.commit()
    return {"id": receipt.id, "number": receipt.number, "orderStatus": po.status if po else None}
