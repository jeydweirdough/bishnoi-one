"""Inventory's demo accounts and demo stock, for development.

`uv run python -m app.tools.users demo` makes the accounts (password
demo1234), one per starting role, and, when there are no products yet, a
small medical-supplies business to try them on: three warehouses, suppliers,
products with batches and variants, and stock that got there the way stock
does, through receipts, so every figure has its movements behind it.

The sign-in page lists the demo accounts that exist here. Neither works in
production.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Adjustment,
    AdjustmentLine,
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
    Supplier,
    SupplierProduct,
    Transfer,
    TransferLine,
    User,
    Warehouse,
)
from app.permissions import ADMINISTRATOR, AUDITOR, PURCHASING, SALES, WAREHOUSE

DEMO_PASSWORD = "demo1234"


@dataclass(frozen=True)
class Demo:
    group: str
    email: str
    name: str
    role: str  # what the sign-in page says they are
    access: str  # the role they're given (app/permissions.py)


DEMO_ACCOUNTS: tuple[Demo, ...] = (
    Demo("Administration", "carmen@pharmacrm.test", "Carmen Villanueva", "Admin · everything, users and roles", ADMINISTRATOR),
    Demo("Warehouse", "iris@pharmacrm.test", "Iris Dela Cruz", "Warehouse · receives, transfers, counts", WAREHOUSE),
    Demo("Warehouse", "bong@pharmacrm.test", "Bong Rivera", "Warehouse · picks, packs, issues", WAREHOUSE),
    Demo("Purchasing", "paz@pharmacrm.test", "Paz Navarro", "Purchasing · suppliers, POs, approvals", PURCHASING),
    Demo("Sales", "ben@pharmacrm.test", "Ben Cruz", "Sales · sees stock, writes orders", SALES),
    Demo("Audit", "aurora@pharmacrm.test", "Aurora Santos", "Auditor · sees everything, changes nothing", AUDITOR),
)


def peso(amount: float) -> int:
    return round(amount * 100)


def seed(db: Session) -> bool:
    """Demo stock, once: only into an inventory with no products. Returns
    whether it made any."""
    from app.stock import Ref, next_number, pick_out, post, resolve_batch, serials_in, serials_out

    if db.scalar(select(func.count()).select_from(Product)):
        return False
    admin = db.scalar(select(User).where(User.email == DEMO_ACCOUNTS[0].email))
    iris = db.scalar(select(User).where(User.email == "iris@pharmacrm.test")) or admin
    if admin is None:
        return False
    today = datetime.now(UTC).date()

    # Where stock is kept.
    places = {}
    for code, name, address, bins in (
        ("MNL", "Manila Warehouse", "Pasig City, Metro Manila", (("A1", "Aisle A, rack 1"), ("A2", "Aisle A, rack 2"), ("COLD", "Cold room"))),
        ("CEB", "Cebu Warehouse", "Mandaue City, Cebu", (("B1", "Bay 1"),)),
        ("DVO", "Davao Warehouse", "Davao City", ()),
    ):
        w = Warehouse(code=code, name=name, address=address)
        db.add(w)
        db.flush()
        main = Location(warehouse_id=w.id, code="MAIN", name="Main area", is_default=True)
        db.add(main)
        for bcode, bname in bins:
            db.add(Location(warehouse_id=w.id, code=bcode, name=bname))
        db.flush()
        places[code] = (w, main)

    # What's sold, and who from.
    medical = Category(name="Medical Supplies")
    pharma = Category(name="Pharmaceuticals")
    db.add_all([medical, pharma])
    db.flush()
    cats = {"Medical Supplies": medical, "Pharmaceuticals": pharma}
    for name, parent in (("Syringes", medical), ("Gloves", medical), ("IV & Infusion", medical), ("Analgesics", pharma), ("Antibiotics", pharma)):
        cats[name] = Category(name=name, parent_id=parent.id)
        db.add(cats[name])
    brands = {n: Brand(name=n) for n in ("BD", "Terumo", "Medline", "Unilab", "Pfizer")}
    db.add_all(brands.values())
    suppliers = {
        "ABC": Supplier(code="ABC", name="ABC Medical Supply", contact_person="Rhea Manalo", email="orders@abcmedical.test", phone="02 8634 1100", address="Quezon City", payment_terms="Net 30", lead_time_days=5),
        "PHX": Supplier(code="PHX", name="Pharmex Distributors", contact_person="Jun Ocampo", email="sales@pharmex.test", phone="02 8812 4455", address="Makati City", payment_terms="Net 45", lead_time_days=10),
        "VIS": Supplier(code="VIS", name="Visayas Health Traders", contact_person="Mae Lim", email="mae@vistraders.test", phone="032 344 7788", address="Cebu City", payment_terms="COD", lead_time_days=3),
    }
    db.add_all(suppliers.values())
    db.flush()

    def product(sku, name, cat, brand, unit, supplier, cost, price, reorder, *, maxs=None, batches=False, expiry=False, serials=False, parent=None, variant=None, attrs=None, ptype="stock", tax=1200):
        p = Product(
            sku=sku, name=name, category_id=cats[cat].id, brand_id=brands[brand].id if brand else None, unit_code=unit, supplier_id=suppliers[supplier].id,
            cost_price=peso(cost), selling_price=peso(price), tax_rate_bp=tax, reorder_point=reorder, min_stock=reorder // 2, max_stock=maxs, reorder_qty=reorder * 2,
            track_batches=batches, track_expiry=expiry, track_serials=serials, parent_id=parent.id if parent else None, variant_label=variant, attributes=attrs or {}, product_type=ptype,
        )
        db.add(p)
        db.flush()
        db.add(SupplierProduct(supplier_id=suppliers[supplier].id, product_id=p.id, price=peso(cost), lead_time_days=suppliers[supplier].lead_time_days))
        return p

    syringe = product("SYR-BD", "BD Syringe", "Syringes", "BD", "pc", "ABC", 0, 0, 0, attrs={"Tip": "Luer-Lok"})
    s1 = product("SYR-BD-1", "BD Syringe 1 mL", "Syringes", "BD", "pc", "ABC", 4.5, 9, 500, maxs=5000, batches=True, expiry=True, parent=syringe, variant="1 mL", attrs={"Volume": "1 mL", "Needle": "26G"})
    s3 = product("SYR-BD-3", "BD Syringe 3 mL", "Syringes", "BD", "pc", "ABC", 5.2, 11, 800, maxs=6000, batches=True, expiry=True, parent=syringe, variant="3 mL", attrs={"Volume": "3 mL", "Needle": "23G"})
    s5 = product("SYR-BD-5", "BD Syringe 5 mL", "Syringes", "BD", "pc", "ABC", 6.1, 13, 600, maxs=5000, batches=True, expiry=True, parent=syringe, variant="5 mL", attrs={"Volume": "5 mL", "Needle": "21G"})
    gloves = product("GLV-NIT-M", "Nitrile Gloves, Medium", "Gloves", "Medline", "box", "ABC", 185, 320, 400, maxs=1500, batches=True, expiry=True, attrs={"Size": "M", "Count": "100 per box", "Powder": "Free"})
    ivset = product("IV-SET-TR", "IV Administration Set", "IV & Infusion", "Terumo", "set", "VIS", 38, 75, 150, maxs=800, batches=True, expiry=True)
    pcm = product("PCM-500", "Paracetamol 500 mg", "Analgesics", "Unilab", "box", "PHX", 95, 165, 200, maxs=1200, batches=True, expiry=True, attrs={"Strength": "500 mg", "Form": "Tablet", "Pack": "100 tablets"})
    amx = product("AMX-500", "Amoxicillin 500 mg", "Antibiotics", "Pfizer", "box", "PHX", 420, 690, 80, maxs=600, batches=True, expiry=True, attrs={"Strength": "500 mg", "Form": "Capsule", "Pack": "100 capsules"})
    pump = product("PUMP-TE", "Infusion Pump TE-171", "IV & Infusion", "Terumo", "pc", "VIS", 48000, 72500, 2, maxs=10, serials=True, attrs={"Power": "AC / battery", "Warranty": "2 years"}, tax=1200)
    db.flush()

    def receive(po, supplier, where, lines, when_days_ago):
        w, loc = places[where]
        r = Receipt(number=next_number(db, "RC"), order_id=po.id if po else None, supplier_id=suppliers[supplier].id, warehouse_id=w.id, location_id=loc.id, received_by_id=iris.id, received_at=datetime.now(UTC) - timedelta(days=when_days_ago), delivery_ref=f"DR-{4000 + len(lines) * 7 + when_days_ago}")
        db.add(r)
        db.flush()
        for p, qty, batch_no, expires, serial_list in lines:
            batch = resolve_batch(db, p, batch_no, manufactured_on=(expires - timedelta(days=730)) if expires else None, expires_on=expires, supplier_id=suppliers[supplier].id) if batch_no else None
            if batch is not None:
                batch.received_at = r.received_at
            if serial_list:
                serials_in(db, p, serial_list, loc, batch)
            m = post(db, iris, kind="receive", product=p, quantity=qty, ref=Ref("receipt", r.id, r.number), location=loc, batch=batch, serials=serial_list)
            m.at = r.received_at
            line = next((x for x in po.lines if x.product_id == p.id), None) if po else None
            if line:
                line.received += qty
            db.add(ReceiptLine(receipt_id=r.id, order_line_id=line.id if line else None, product_id=p.id, batch_id=batch.id if batch else None, quantity=qty, unit_cost=p.cost_price, serials=serial_list or []))
        if po:
            po.status = "received" if all(x.received >= x.quantity for x in po.lines) else "partial"

    def po(supplier, where, lines, days_ago, expected_in, placed=True):
        order = PurchaseOrder(number=next_number(db, "PO"), supplier_id=suppliers[supplier].id, warehouse_id=places[where][0].id, created_by_id=admin.id, status="ordered" if placed else "draft",
                              ordered_on=today - timedelta(days=days_ago) if placed else None, expected_on=today - timedelta(days=days_ago) + timedelta(days=expected_in), ordered_by_id=admin.id if placed else None)
        order.lines = [PurchaseOrderLine(position=i, product_id=p.id, quantity=q, unit_cost=p.cost_price) for i, (p, q) in enumerate(lines)]
        db.add(order)
        db.flush()
        return order

    # Stock that came in on orders, over the last few months.
    d = today
    po1 = po("ABC", "MNL", [(s1, 3000), (s3, 4000), (s5, 2500), (gloves, 600)], 120, 5)
    receive(po1, "ABC", "MNL", [(s1, 3000, "BD1-2604", d + timedelta(days=600), None), (s3, 4000, "BD3-2604", d + timedelta(days=640), None), (s5, 2500, "BD5-2604", d + timedelta(days=620), None), (gloves, 600, "MDL-2603", d + timedelta(days=400), None)], 115)
    po2 = po("PHX", "MNL", [(pcm, 900), (amx, 300)], 90, 10)
    receive(po2, "PHX", "MNL", [(pcm, 500, "PCM-260821", d + timedelta(days=45), None), (pcm, 400, "PCM-261102", d + timedelta(days=500), None), (amx, 300, "AMX-2605", d + timedelta(days=75), None)], 82)
    po3 = po("VIS", "CEB", [(ivset, 400), (pump, 4), (s3, 1500)], 60, 3)
    receive(po3, "VIS", "CEB", [(ivset, 400, "TR-IV-2606", d + timedelta(days=300), None), (pump, 4, None, None, ["TE171-00481", "TE171-00482", "TE171-00483", "TE171-00484"])], 57)
    # A delivery still coming: 10 IV sets and 50 boxes of gloves, part-received.
    po4 = po("ABC", "MNL", [(ivset, 200), (gloves, 400), (s5, 2000)], 9, 5)
    receive(po4, "ABC", "MNL", [(gloves, 250, "MDL-2609", d + timedelta(days=700), None)], 3)
    po("PHX", "DVO", [(pcm, 300), (amx, 100)], 0, 10, placed=False)
    # An old batch that has expired on the shelf.
    receive(None, "PHX", "DVO", [(pcm, 60, "PCM-250310", d - timedelta(days=12), None), (amx, 40, "AMX-2511", d + timedelta(days=20), None)], 200)
    db.flush()

    # Stock that went out.
    for recipient, kind, where, lines, days_ago in (
        ("St. Luke's Family Clinic", "sale", "MNL", [(s3, 1200), (gloves, 180)], 40),
        ("Emergency Department", "department", "MNL", [(s1, 900), (pcm, 150)], 25),
        ("Cebu Doctors' Hospital", "sale", "CEB", [(ivset, 380), (pump, 1)], 12),
        ("Riverside Medical Center", "sale", "MNL", [(amx, 240), (s5, 900)], 6),
    ):
        o = Order(number=next_number(db, "SO" if kind == "sale" else "IS"), kind=kind, recipient=recipient, warehouse_id=places[where][0].id, created_by_id=admin.id, confirmed_by_id=admin.id, issued_by_id=iris.id)
        o.lines = [OrderLine(position=i, product_id=p.id, quantity=q, unit_price=p.selling_price) for i, (p, q) in enumerate(lines)]
        db.add(o)
        db.flush()
        for line in o.lines:
            serials = ["TE171-00481"] if line.product_id == pump.id else []
            if serials:
                serials_out(db, pump, serials, o.warehouse_id, "issued")
            line.picks = pick_out(db, iris, kind="issue", product=line.product, warehouse_id=o.warehouse_id, quantity=line.quantity, ref=Ref("order", o.id, o.number), note=f"To {recipient}", serials=serials)
            line.serials = serials
        moment = datetime.now(UTC) - timedelta(days=days_ago)
        o.status, o.confirmed_at, o.issued_at = "issued", moment, moment
    db.flush()

    # An order holding stock: the IV sets in Cebu are all spoken for.
    held = Order(number=next_number(db, "SO"), kind="sale", recipient="Vicente Sotto Memorial", warehouse_id=places["CEB"][0].id, needed_on=today + timedelta(days=2), created_by_id=admin.id, confirmed_by_id=admin.id, status="confirmed", confirmed_at=datetime.now(UTC))
    held.lines = [OrderLine(position=0, product_id=ivset.id, quantity=20, unit_price=ivset.selling_price)]
    db.add(held)
    db.flush()
    post(db, admin, kind="reserve", product=ivset, quantity=-20, ref=Ref("order", held.id, held.number), warehouse_id=held.warehouse_id, note="For Vicente Sotto Memorial")
    draft = Order(number=next_number(db, "SO"), kind="sale", recipient="Mabuhay Drugstore", warehouse_id=places["MNL"][0].id, needed_on=today + timedelta(days=5), created_by_id=admin.id)
    draft.lines = [OrderLine(position=0, product_id=pcm.id, quantity=50, unit_price=pcm.selling_price), OrderLine(position=1, product_id=gloves.id, quantity=20, unit_price=gloves.selling_price)]
    db.add(draft)

    # Syringes on their way to Cebu.
    t = Transfer(number=next_number(db, "TR"), from_warehouse_id=places["MNL"][0].id, to_warehouse_id=places["CEB"][0].id, created_by_id=iris.id, requested_by_id=iris.id, approved_by_id=admin.id, dispatched_by_id=iris.id,
                 requested_at=datetime.now(UTC) - timedelta(days=2), approved_at=datetime.now(UTC) - timedelta(days=2), dispatched_at=datetime.now(UTC) - timedelta(days=1), status="in_transit")
    t.lines = [TransferLine(position=0, product_id=s3.id, quantity=100)]
    db.add(t)
    db.flush()
    t.lines[0].picks = pick_out(db, iris, kind="transfer_out", product=s3, warehouse_id=t.from_warehouse_id, quantity=100, ref=Ref("transfer", t.id, t.number), note="To Cebu Warehouse")
    asked = Transfer(number=next_number(db, "TR"), from_warehouse_id=places["MNL"][0].id, to_warehouse_id=places["DVO"][0].id, created_by_id=iris.id, requested_by_id=iris.id, requested_at=datetime.now(UTC), status="requested")
    asked.lines = [TransferLine(position=0, product_id=gloves.id, quantity=50), TransferLine(position=1, product_id=s1.id, quantity=300)]
    db.add(asked)

    # A count of 3 missing gloves, waiting for someone who may approve it.
    glove_batch = resolve_batch(db, gloves, "MDL-2603")
    pending = Adjustment(number=next_number(db, "ADJ"), warehouse_id=places["MNL"][0].id, reason="lost", notes="Shelf count short by 3 boxes", created_by_id=iris.id)
    pending.lines = [AdjustmentLine(position=0, product_id=gloves.id, location_id=places["MNL"][1].id, batch_id=glove_batch.id, quantity=-3)]
    db.add(pending)
    db.flush()
    return True

