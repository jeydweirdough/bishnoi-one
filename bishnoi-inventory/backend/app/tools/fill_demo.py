"""Fills a demo company's inventory with a few months of a small warehouse's
work, so every list runs past one page and every board has cards in each column.

    uv run python -m app.tools.users --company northwind demo     # first: the demo accounts and stock
    uv run python -m app.tools.fill_demo --company northwind

About 40 more products, 3 more suppliers, 30 purchase orders (most received,
with batches and expiry dates), 60 orders (issued, held, picking, draft), 12
transfers and 10 adjustments. Stock moves through the same ledger the screens
use (app/stock.py), so every balance adds up.

For development only. Into a company whose every account is a demo one
(@….test); a company with real people in it (a local copy of GetMeds) only
when asked with --real, and then its own products are used and none are
added. Stock moves can't be taken back one by one, so keep a copy of the
database first (the way back is that copy), and never copy a filled local
database up to the live one.

    uv run python -m app.tools.fill_demo --company getmeds --real
"""

import random
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import (
    Adjustment,
    AdjustmentLine,
    AuditEntry,
    Batch,
    Brand,
    Category,
    Location,
    Order,
    OrderLine,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Receipt,
    ReceiptLine,
    Stock,
    Supplier,
    SupplierProduct,
    Transfer,
    TransferLine,
    User,
    Warehouse,
)
from app.routers.adjustments import post_adjustment
from app.stock import Ref, available, next_number, pick_out, post, resolve_batch
from app.tenants import for_tool

TOOL = "fill demo tool"

# sku, name, category, brand, unit, cost, price, reorder point
PRODUCTS = (
    ("CTZ-10", "Cetirizine 10 mg", "Pharmaceuticals", "Unilab", "box", 210, 380, 120),
    ("LOR-10", "Loratadine 10 mg", "Pharmaceuticals", "Unilab", "box", 240, 420, 100),
    ("IBU-400", "Ibuprofen 400 mg", "Analgesics", "Unilab", "box", 160, 290, 150),
    ("MEF-500", "Mefenamic Acid 500 mg", "Analgesics", "Unilab", "box", 180, 320, 150),
    ("CEF-500", "Cefalexin 500 mg", "Antibiotics", "Pfizer", "box", 520, 860, 60),
    ("AZI-500", "Azithromycin 500 mg", "Antibiotics", "Pfizer", "box", 980, 1550, 40),
    ("CIP-500", "Ciprofloxacin 500 mg", "Antibiotics", "Pfizer", "box", 610, 990, 50),
    ("MET-500", "Metformin 500 mg", "Pharmaceuticals", "Unilab", "box", 230, 410, 200),
    ("AML-5", "Amlodipine 5 mg", "Pharmaceuticals", "Pfizer", "box", 260, 470, 180),
    ("LOS-50", "Losartan 50 mg", "Pharmaceuticals", "Unilab", "box", 310, 560, 160),
    ("ATV-20", "Atorvastatin 20 mg", "Pharmaceuticals", "Pfizer", "box", 450, 790, 120),
    ("OMP-20", "Omeprazole 20 mg", "Pharmaceuticals", "Unilab", "box", 280, 500, 140),
    ("SAL-NEB", "Salbutamol Nebule 2.5 mg", "Pharmaceuticals", "Unilab", "box", 340, 590, 80),
    ("ORS-SAC", "Oral Rehydration Salts", "Pharmaceuticals", "Unilab", "box", 90, 160, 200),
    ("VIT-C500", "Ascorbic Acid 500 mg", "Pharmaceuticals", "Unilab", "box", 120, 220, 250),
    ("ZNC-SYR", "Zinc Sulfate Syrup 60 mL", "Pharmaceuticals", "Unilab", "bottle", 65, 120, 150),
    ("PCM-SYR", "Paracetamol Syrup 60 mL", "Analgesics", "Unilab", "bottle", 55, 105, 200),
    ("AMX-SYR", "Amoxicillin Suspension 60 mL", "Antibiotics", "Pfizer", "bottle", 85, 150, 120),
    ("INS-RAP", "Insulin Rapid 10 mL", "Pharmaceuticals", "Pfizer", "vial", 690, 1150, 30),
    ("HEP-5K", "Heparin 5,000 IU", "Pharmaceuticals", "Pfizer", "vial", 210, 380, 40),
    ("NSS-1L", "Sodium Chloride 0.9% 1 L", "IV & Infusion", "Terumo", "bottle", 75, 140, 300),
    ("D5W-1L", "Dextrose 5% in Water 1 L", "IV & Infusion", "Terumo", "bottle", 80, 150, 250),
    ("LRS-1L", "Lactated Ringer's 1 L", "IV & Infusion", "Terumo", "bottle", 82, 155, 250),
    ("IVC-22", "IV Cannula 22G", "IV & Infusion", "Terumo", "pc", 28, 55, 400),
    ("IVC-20", "IV Cannula 20G", "IV & Infusion", "Terumo", "pc", 28, 55, 400),
    ("GLV-NIT-S", "Nitrile Gloves, Small", "Gloves", "Medline", "box", 185, 320, 300),
    ("GLV-NIT-L", "Nitrile Gloves, Large", "Gloves", "Medline", "box", 185, 320, 300),
    ("GLV-LTX-M", "Latex Gloves, Medium", "Gloves", "Medline", "box", 150, 270, 300),
    ("GLV-SUR-7", "Surgical Gloves, Size 7", "Gloves", "Medline", "pair", 22, 45, 500),
    ("MSK-3PLY", "Face Mask, 3-ply", "Medical Supplies", "Medline", "box", 95, 180, 400),
    ("MSK-N95", "N95 Respirator", "Medical Supplies", "Medline", "box", 650, 1100, 60),
    ("GAU-4X4", "Gauze Pads 4 x 4", "Medical Supplies", "Medline", "pack", 70, 130, 300),
    ("TAP-MIC", "Micropore Tape 1 in", "Medical Supplies", "Medline", "roll", 35, 70, 300),
    ("ALC-70", "Isopropyl Alcohol 70% 500 mL", "Medical Supplies", "Unilab", "bottle", 65, 125, 300),
    ("BET-120", "Povidone-Iodine 120 mL", "Medical Supplies", "Unilab", "bottle", 95, 175, 150),
    ("SYR-BD-10", "BD Syringe 10 mL", "Syringes", "BD", "pc", 7, 15, 600),
    ("NDL-23", "Hypodermic Needle 23G", "Syringes", "BD", "pc", 2, 5, 1000),
    ("INS-SYR", "Insulin Syringe 1 mL", "Syringes", "BD", "pc", 6, 12, 800),
    ("THR-DIG", "Digital Thermometer", "Medical Supplies", "Medline", "pc", 120, 250, 50),
    ("BPM-ARM", "Blood Pressure Monitor", "Medical Supplies", "Medline", "pc", 1450, 2490, 10),
)
SUPPLIERS = (
    ("MDX", "MedDirect Philippines", "Carla Rivera", "Net 30", 7, "Taguig City"),
    ("ZPH", "Zuellig Pharma Partners", "Nico Santos", "Net 60", 14, "Makati City"),
    ("MIN", "Mindanao Medical Trading", "Ruel Abad", "COD", 4, "Davao City"),
)
RECIPIENTS = (
    "Mercury Drug Pasig", "St. Luke's Family Clinic", "Rose Pharmacy Cebu", "Asian Hospital", "Riverside Medical Center",
    "Southstar Drug Makati", "Healthway Clinic Taguig", "Our Lady of Lourdes Hospital", "Generika Drugstore Marikina",
    "Davao Doctors Hospital", "Capitol Medical Center", "Bethany Hospital", "Medical City Clinic Pasig", "Unciano Medical Center",
)
DEPARTMENTS = ("Emergency Department", "Operating Room", "Pediatrics Ward", "Outpatient Pharmacy", "Medical Mission")


def refuse_real(db: Session, real_ok: bool) -> None:
    if get_settings().is_production:
        sys.exit("Demo records are for development only (ENVIRONMENT is production; run with ENVIRONMENT=development).")
    real = db.scalar(select(func.count()).select_from(User).where(~User.email.like("%.test")))
    if real and not real_ok:
        sys.exit(f"Refused: this company has {real} account(s) that aren't demo ones. Say --real to fill it all the same (with its own products).")
    if not db.scalar(select(func.count()).select_from(Product)):
        sys.exit("No demo stock yet. First: uv run python -m app.tools.users --company <name> demo")
    if db.scalar(select(func.count()).select_from(AuditEntry).where(AuditEntry.action == "demo.filled")):
        sys.exit("Already filled. Delete the company's database file to start again.")


def fill(db: Session, rnd: random.Random, real: bool) -> None:
    now = datetime.now(UTC)
    today = now.date()
    people = {u.email: u for u in db.scalars(select(User))}
    admin = people["carmen@pharmacrm.test"]
    iris = people.get("iris@pharmacrm.test", admin)
    bong = people.get("bong@pharmacrm.test", iris)
    paz = people.get("paz@pharmacrm.test", admin)
    ben = people.get("ben@pharmacrm.test", admin)
    warehouses = list(db.scalars(select(Warehouse).order_by(Warehouse.code)))
    main_of = {w.id: db.scalar(select(Location).where(Location.warehouse_id == w.id, Location.is_default)) for w in warehouses}
    manila = next(w for w in warehouses if w.code == "MNL")
    cats = {c.name: c for c in db.scalars(select(Category))}
    brands = {b.name: b for b in db.scalars(select(Brand))}
    suppliers = list(db.scalars(select(Supplier)))
    for code, name, person, terms, lead, city in () if real else SUPPLIERS:
        s = Supplier(code=code, name=name, contact_person=person, email=f"orders@{code.lower()}.test", phone=f"02 8{rnd.randint(100, 999)} {rnd.randint(1000, 9999)}",
                     address=city, payment_terms=terms, lead_time_days=lead)
        db.add(s)
        suppliers.append(s)
    db.flush()

    products: list[Product] = []
    if real:
        # The company's own catalogue: what has a cost, isn't a group, and has no serial numbers to make up.
        products = list(db.scalars(select(Product).where(Product.cost_price > 0, Product.track_serials.is_(False), Product.status == "active")))
        if not products:
            sys.exit("No products with a cost to stock.")
    for sku, name, cat, brand, unit, cost, price, reorder in () if real else PRODUCTS:
        supplier = rnd.choice(suppliers)
        dated = cat not in ("Medical Supplies",) or sku.startswith(("ALC", "BET"))
        p = Product(sku=sku, name=name, category_id=cats[cat].id, brand_id=brands[brand].id, unit_code=unit, supplier_id=supplier.id,
                    cost_price=cost * 100, selling_price=price * 100, tax_rate_bp=1200, reorder_point=reorder, min_stock=reorder // 2,
                    max_stock=reorder * 8, reorder_qty=reorder * 2, track_batches=dated, track_expiry=dated)
        db.add(p)
        db.flush()
        db.add(SupplierProduct(supplier_id=supplier.id, product_id=p.id, price=p.cost_price, lead_time_days=supplier.lead_time_days))
        products.append(p)
    # The demo's own stocked products join in (not the group, not the serial-numbered pump).
    products += [] if real else [p for p in db.scalars(select(Product).where(Product.sku.in_(("SYR-BD-1", "SYR-BD-3", "SYR-BD-5", "GLV-NIT-M", "IV-SET-TR", "PCM-500", "AMX-500"))))]
    db.flush()

    # Purchase orders over four months: most received, some in part, some still coming, a few drafts.
    pos = 0
    for i in range(30):
        supplier = rnd.choice(suppliers)
        w = manila if rnd.random() < 0.6 else rnd.choice(warehouses)
        days_ago = rnd.randint(2, 120)
        state = "draft" if i < 3 else "ordered" if i < 7 else "partial" if i < 11 else "received"
        if state in ("draft", "ordered"):
            days_ago = rnd.randint(0, 12)
        picked = rnd.sample(products, k=rnd.randint(2, 5))
        order = PurchaseOrder(number=next_number(db, "PO"), supplier_id=supplier.id, warehouse_id=w.id, created_by_id=paz.id,
                              status="draft" if state == "draft" else "ordered", ordered_on=None if state == "draft" else today - timedelta(days=days_ago),
                              expected_on=today - timedelta(days=days_ago) + timedelta(days=supplier.lead_time_days), ordered_by_id=None if state == "draft" else paz.id)
        order.lines = [PurchaseOrderLine(position=n, product_id=p.id, quantity=(p.reorder_point or rnd.randint(40, 160)) * rnd.choice((1, 2, 3)), unit_cost=p.cost_price) for n, p in enumerate(picked)]
        db.add(order)
        db.flush()
        pos += 1
        if state in ("partial", "received"):
            when = now - timedelta(days=max(days_ago - supplier.lead_time_days, 0), hours=rnd.randint(0, 6))
            loc = main_of[w.id]
            r = Receipt(number=next_number(db, "RC"), order_id=order.id, supplier_id=supplier.id, warehouse_id=w.id, location_id=loc.id,
                        received_by_id=iris.id, received_at=when, delivery_ref=f"DR-{rnd.randint(10000, 99999)}")
            db.add(r)
            db.flush()
            for line in order.lines:
                p = next(x for x in picked if x.id == line.product_id)
                qty = line.quantity if state == "received" else line.quantity // 2
                batch = None
                if p.track_batches:
                    expires = today + timedelta(days=rnd.choice((25, 60, 120, 300, 500, 700)))
                    batch = resolve_batch(db, p, f"{p.sku[:3]}-{when:%y%m}{rnd.randint(10, 99)}", manufactured_on=expires - timedelta(days=730), expires_on=expires, supplier_id=supplier.id)
                    batch.received_at = when
                m = post(db, iris, kind="receive", product=p, quantity=qty, ref=Ref("receipt", r.id, r.number), location=loc, batch=batch)
                m.at = when
                line.received += qty
                db.add(ReceiptLine(receipt_id=r.id, order_line_id=line.id, product_id=p.id, batch_id=batch.id if batch else None, quantity=qty, unit_cost=p.cost_price))
            order.status = "received" if state == "received" else "partial"
    db.flush()

    def in_stock(w: Warehouse) -> list[Product]:
        ids = set(db.scalars(select(Stock.product_id).where(Stock.warehouse_id == w.id, Stock.on_hand > 0)))
        return [p for p in products if p.id in ids]

    # Orders: issued over three months, then some held, some being picked, some drafts.
    orders = 0
    for i in range(60):
        w = manila if rnd.random() < 0.65 else rnd.choice(warehouses)
        stocked = in_stock(w)
        if len(stocked) < 2:
            continue
        kind = rnd.choices(("sale", "department", "internal", "project", "distribution"), weights=(8, 3, 1, 1, 1))[0]
        recipient = rnd.choice(DEPARTMENTS if kind == "department" else RECIPIENTS)
        state = "issued" if i < 42 else "confirmed" if i < 50 else "picking" if i < 54 else "draft"
        o = Order(number=next_number(db, "SO" if kind == "sale" else "IS"), kind=kind, recipient=recipient, warehouse_id=w.id,
                  needed_on=today + timedelta(days=rnd.randint(1, 10)) if state != "issued" else None, created_by_id=ben.id)
        lines = []
        for n, p in enumerate(rnd.sample(stocked, k=min(len(stocked), rnd.randint(1, 4)))):
            free = available(db, p.id, w.id)
            if free < 2:
                continue
            lines.append(OrderLine(position=n, product_id=p.id, quantity=max(1, min(free // 4, rnd.randint(5, 120))), unit_price=p.selling_price))
        if not lines:
            continue
        o.lines = lines
        db.add(o)
        db.flush()
        orders += 1
        moment = now - timedelta(days=rnd.randint(1, 90), hours=rnd.randint(0, 8)) if state == "issued" else now - timedelta(hours=rnd.randint(1, 72))
        if state == "draft":
            continue
        o.confirmed_by_id, o.confirmed_at = admin.id, moment
        if state == "issued":
            for line in o.lines:
                line.picks = pick_out(db, bong, kind="issue", product=line.product, warehouse_id=w.id, quantity=line.quantity, ref=Ref("order", o.id, o.number), note=f"To {recipient}")
            o.status, o.issued_by_id, o.issued_at = "issued", bong.id, moment
        else:
            for line in o.lines:
                post(db, admin, kind="reserve", product=line.product, quantity=-line.quantity, ref=Ref("order", o.id, o.number), warehouse_id=w.id, note=f"For {recipient}")
            o.status = state
    db.flush()

    # Transfers between warehouses: received, on the way, approved, asked for.
    transfers = 0
    for i in range(12):
        src = manila if rnd.random() < 0.7 else rnd.choice(warehouses)
        dst = rnd.choice([w for w in warehouses if w.id != src.id])
        stocked = [p for p in in_stock(src) if available(db, p.id, src.id) >= 20]
        if not stocked:
            continue
        state = "received" if i < 5 else "in_transit" if i < 8 else "approved" if i < 10 else "requested"
        asked = now - timedelta(days=rnd.randint(1, 45) if state == "received" else rnd.randint(0, 4))
        t = Transfer(number=next_number(db, "TR"), from_warehouse_id=src.id, to_warehouse_id=dst.id, created_by_id=iris.id, requested_by_id=iris.id, requested_at=asked, status=state)
        t.lines = [TransferLine(position=n, product_id=p.id, quantity=max(5, available(db, p.id, src.id) // 5)) for n, p in enumerate(rnd.sample(stocked, k=min(len(stocked), rnd.randint(1, 3))))]
        db.add(t)
        db.flush()
        transfers += 1
        if state == "requested":
            continue
        t.approved_by_id, t.approved_at = admin.id, asked + timedelta(hours=2)
        if state == "approved":
            continue
        t.dispatched_by_id, t.dispatched_at = iris.id, asked + timedelta(hours=5)
        for line in t.lines:
            line.picks = pick_out(db, iris, kind="transfer_out", product=line.product, warehouse_id=src.id, quantity=line.quantity, ref=Ref("transfer", t.id, t.number), note=f"To {dst.name}")
        if state == "received":
            for line in t.lines:
                for pick in line.picks:
                    batch = db.get(Batch, pick["batchId"]) if pick.get("batchId") else None
                    post(db, iris, kind="transfer_in", product=line.product, quantity=pick["quantity"], ref=Ref("transfer", t.id, t.number), location=main_of[dst.id], batch=batch, note=f"From {src.name}")
            t.received_by_id, t.received_at = iris.id, asked + timedelta(days=rnd.randint(1, 3))
    db.flush()

    # Adjustments: counts, damage and expiry, most posted, a few waiting for approval.
    adjustments = 0
    for i in range(10):
        w = rnd.choice(warehouses)
        rows = [r for r in db.scalars(select(Stock).where(Stock.warehouse_id == w.id, Stock.on_hand > 10)) if not r.product.track_serials]
        if not rows:
            continue
        row = rnd.choice(rows)
        reason = rnd.choice(("count", "damaged", "expired", "found", "lost"))
        qty = rnd.randint(1, 6) * (1 if reason == "found" else -1 if reason != "count" else rnd.choice((1, -1)))
        if qty < 0 and available(db, row.product_id, w.id) < -qty:
            continue
        a = Adjustment(number=next_number(db, "ADJ"), warehouse_id=w.id, reason=reason, notes=rnd.choice(("Shelf count", "Found during cycle count", "Damaged in handling", "Past expiry")), created_by_id=iris.id)
        a.lines = [AdjustmentLine(position=0, product_id=row.product_id, location_id=row.location_id, batch_id=row.batch_id, quantity=qty)]
        db.add(a)
        db.flush()
        adjustments += 1
        if i >= 3:
            post_adjustment(db, admin, a)

    summary = ("" if real else f"{len(PRODUCTS)} products, {len(SUPPLIERS)} suppliers, ") + f"{pos} purchase orders, {orders} orders, {transfers} transfers, {adjustments} adjustments"
    audit(db, TOOL, "demo.filled", target=summary)
    db.commit()
    print(f"Made {summary}.")


def main() -> int:
    company, url = for_tool(sys.argv)
    print(f"Company: {company}")
    engine = make_engine(url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        refuse_real(db, "--real" in sys.argv)
        fill(db, random.Random(7), "--real" in sys.argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
