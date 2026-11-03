"""Seed products, prices, and zero stocks from BEA Price List U0725 into Bishnoi Inventory & CRM.

Source:
  C:\\Users\\Getmeds Backend\\Downloads\\Price List 2026 Finance (1).xlsx (Sheet: "BEA Price List U0725")

Targets:
  1. Bishnoi Inventory (SQLite & Postgres): 64 products, categories, brands, units, VAT rates,
     SRP & distributor prices, attributes, and 0 stock across all warehouses & locations.
  2. Bishnoi CRM (SQLite & Postgres): Products and 5 price tiers (DOCTOR, PATIENT, DISTRIBUTOR, TRADE, SRP).
  3. Office Server Seed (Desktop/bishnoi-one-seed): inventory-getmeds.db & crm-getmeds.db.

Usage:
  # Dry run (inspect what would be added/updated without saving):
  uv run python -m app.tools.seed_products

  # Apply changes to local databases:
  uv run python -m app.tools.seed_products --apply

  # Apply to all targets (including Desktop/bishnoi-one-seed and Neon if configured):
  uv run python -m app.tools.seed_products --apply --all-databases
"""

import argparse
from datetime import UTC, datetime
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import uuid

from app.tools.bea_catalog import BEA_PRODUCTS

# Safe console encoding for UTF-8 without disrupting pytest/test runners
def _init_stdout():
    if "pytest" not in sys.modules and sys.stdout and hasattr(sys.stdout, "buffer"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

DEFAULT_EXCEL_PATH = r"C:\Users\Getmeds Backend\Downloads\Price List 2026 Finance (1).xlsx"
DEFAULT_SHEET = "BEA Price List U0725"

APP_DIR = Path(__file__).resolve().parent.parent.parent  # bishnoi-inventory/backend
MODULE_DIR = APP_DIR.parent  # bishnoi-inventory
REPO_DIR = MODULE_DIR.parent  # bishnoi-one

INV_GETMEDS_SQLITE = APP_DIR / ".data" / "inventory-getmeds.db"
INV_BASE_SQLITE = APP_DIR / ".data" / "inventory.db"
CRM_GETMEDS_SQLITE = REPO_DIR / "bishnoi-crm" / "backend" / ".data" / "crm-getmeds.db"
CRM_BASE_SQLITE = REPO_DIR / "bishnoi-crm" / "backend" / ".data" / "crm.db"

SEED_DIR = Path(r"C:\Users\Getmeds Backend\Desktop\bishnoi-one-seed")
SEED_INV_SQLITE = SEED_DIR / "inventory-getmeds.db"
SEED_CRM_SQLITE = SEED_DIR / "crm-getmeds.db"


def make_backup(file_path: Path | str) -> Path | None:
    path = Path(file_path)
    if not path.exists():
        return None
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{path.stem}_{ts}{path.suffix}.bak"
    shutil.copy2(path, backup_path)
    return backup_path


def to_centavos(val: any) -> int:
    if val is None:
        return 0
    try:
        if isinstance(val, (int, float)):
            return int(round(float(val) * 100))
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return int(round(float(cleaned) * 100)) if cleaned else 0
    except Exception:
        return 0


def clean_sku(brand: str, generic: str, strength: str) -> str:
    """Generate a clean, standardized, collision-free SKU matching existing DB patterns."""
    b_upper = (brand or "").strip()
    s_upper = (strength or "").strip()
    g_upper = (generic or "").strip()

    # Extract specific parenthesized dose (e.g. 150 mg/15 ml) to differentiate variants
    m = re.search(r"\((\d+(?:\.\d+)?\s*(?:mg|g|iu|mcg))", s_upper, re.IGNORECASE)
    dose_str = m.group(1).replace(" ", "").upper() if m else ""

    # Base clean: strip brackets like [COLD CHAIN], [REGULATED], etc., and parentheses
    s_clean = f"{b_upper} {s_upper}".strip()
    s_clean = re.sub(r"\[.*?\]|\(.*?\)", "", s_clean)
    s_clean = re.sub(r"[^a-zA-Z0-9]+", "-", s_clean).strip("-").upper()

    parts = s_clean.split("-")
    dedup = []
    for p in parts:
        if not dedup or p != dedup[-1]:
            dedup.append(p)
    base = "-".join(dedup)

    # For injectables with multiple sizes (CarboGet, OxaliGet, PacliGet, Brevixel), put dose in SKU
    if dose_str and any(k in base for k in ("CARBO", "OXALI", "PACLI", "BREVIXEL")):
        p_list = base.split("-")
        brand_head = p_list[0]
        rest = "-".join(p_list[1:])
        base = f"{brand_head}-{dose_str}-{rest}"
    elif not base or base in ("GETMEDS", "2MG"):
        s_clean = f"{b_upper} {g_upper} {s_upper}".strip()
        s_clean = re.sub(r"\[.*?\]|\(.*?\)", "", s_clean)
        s_clean = re.sub(r"[^a-zA-Z0-9]+", "-", s_clean).strip("-").upper()
        parts = s_clean.split("-")
        dedup = []
        for p in parts:
            if not dedup or p != dedup[-1]:
                dedup.append(p)
        base = "-".join(dedup)

    return base[:35].rstrip("-")


UNIT_MAP = {
    "ampoule": "ampule",
    "ampule": "ampule",
    "vial": "vial",
    "box": "box",
    "piece": "pc",
    "unit": "pc",
    "pouch": "pack",
    "pack": "pack",
    "bottle": "bottle",
    "tablet": "tablet",
    "capsule": "capsule",
    "sachet": "sachet",
    "set": "set",
    "pfs": "pfs",
    "pen": "pen",
}


def get_catalog_products() -> list[dict]:
    """Return all 64 products directly from the embedded Python catalog."""
    products = []
    for p in BEA_PRODUCTS:
        p_copy = dict(p)
        p_copy["id"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"bishnoi.product.{p['sku']}"))
        p_copy["is_vat"] = p.get("tax_rate_bp", 0) > 0
        products.append(p_copy)
    return products


def load_excel_products(file_path: str = DEFAULT_EXCEL_PATH, sheet_name: str = DEFAULT_SHEET) -> list[dict]:
    """Optional loader if an Excel file is explicitly supplied."""
    excel_file = Path(file_path)
    if not excel_file.exists():
        return get_catalog_products()

    import openpyxl
    wb = openpyxl.load_workbook(file_path, data_only=True)
    if sheet_name not in wb.sheetnames:
        raise ValueError(f"Sheet {sheet_name!r} not found. Available sheets: {wb.sheetnames}")
    ws = wb[sheet_name]

    products = []
    for r in range(3, ws.max_row + 1):
        account = str(ws.cell(r, 1).value or "").strip()
        inv_type = str(ws.cell(r, 2).value or "").strip()
        tax = str(ws.cell(r, 3).value or "").strip()
        category = str(ws.cell(r, 4).value or "").strip()
        generic = str(ws.cell(r, 5).value or "").strip()
        brand = str(ws.cell(r, 6).value or "").strip()
        strength = str(ws.cell(r, 7).value or "").strip()
        form = str(ws.cell(r, 8).value or "").strip()
        unit_raw = str(ws.cell(r, 9).value or "").strip()
        pack_size = str(ws.cell(r, 10).value or "").strip()
        count = ws.cell(r, 11).value
        shelf_life = str(ws.cell(r, 12).value or "").strip()

        # Stop when notes section is reached
        if account.startswith(">>") or (not brand and not generic):
            continue

        doc_u = ws.cell(r, 13).value
        doc_p = ws.cell(r, 14).value
        doc_deals = ws.cell(r, 15).value
        pat_u = ws.cell(r, 16).value
        pat_p = ws.cell(r, 17).value
        pat_pct = ws.cell(r, 18).value
        pat_deals = ws.cell(r, 19).value
        dist_u = ws.cell(r, 20).value
        dist_p = ws.cell(r, 21).value
        dist_deals = ws.cell(r, 22).value
        trade_u = ws.cell(r, 23).value
        trade_p = ws.cell(r, 24).value
        srp_u = ws.cell(r, 25).value
        srp_p = ws.cell(r, 26).value

        sku = clean_sku(brand, generic, strength)
        unit_code = UNIT_MAP.get(unit_raw.lower(), "pc")

        # VAT rules: 'VAT' is 12% (1200 basis points). 'VE' and '-' are exempt (0 bp).
        is_vat = tax.upper() == "VAT"
        tax_rate_bp = 1200 if is_vat else 0

        # Deterministic UUID for product
        prod_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"bishnoi.product.{sku}"))

        p_obj = {
            "row": r,
            "id": prod_uuid,
            "sku": sku,
            "name": brand,
            "account": account,
            "inventory_type": inv_type,
            "category": category,
            "generic": generic,
            "strength": strength,
            "form": form,
            "unit_raw": unit_raw or "Piece",
            "unit_code": unit_code,
            "pack_size": pack_size,
            "count": int(count) if count and isinstance(count, (int, float)) else 1,
            "shelf_life": shelf_life,
            "tax": tax,
            "is_vat": is_vat,
            "tax_rate_bp": tax_rate_bp,
            "doc_u_cents": to_centavos(doc_u),
            "doc_p_cents": to_centavos(doc_p),
            "doc_deals": str(doc_deals).strip() if doc_deals else None,
            "pat_u_cents": to_centavos(pat_u),
            "pat_p_cents": to_centavos(pat_p),
            "pat_pct": float(pat_pct) if pat_pct and isinstance(pat_pct, (int, float)) else None,
            "pat_deals": str(pat_deals).strip() if pat_deals else None,
            "dist_u_cents": to_centavos(dist_u),
            "dist_p_cents": to_centavos(dist_p),
            "dist_deals": str(dist_deals).strip() if dist_deals else None,
            "trade_u_cents": to_centavos(trade_u),
            "trade_p_cents": to_centavos(trade_p),
            "srp_u_cents": to_centavos(srp_u),
            "srp_p_cents": to_centavos(srp_p),
        }
        products.append(p_obj)

    return products


def seed_inventory_sqlite(db_path: Path | str, products: list[dict], apply: bool = False) -> dict:
    path = Path(db_path)
    if not path.exists():
        return {"status": "skipped", "reason": f"File does not exist: {path}"}

    if apply:
        make_backup(path)

    conn = sqlite3.connect(path)
    c = conn.cursor()
    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    # 1. Ensure Warehouses & Locations exist
    c.execute("SELECT id, name FROM nbin_warehouses")
    warehouses = c.fetchall()
    if not warehouses:
        wh_id = str(uuid.uuid4())
        if apply:
            c.execute(
                "INSERT INTO nbin_warehouses (id, code, name, is_active, created_at, updated_at) VALUES (?, 'MAIN', 'Main Warehouse', 1, ?, ?)",
                (wh_id, now_str, now_str),
            )
        warehouses = [(wh_id, "Main Warehouse")]

    c.execute("SELECT id, warehouse_id FROM nbin_locations")
    loc_by_wh = {}
    for loc_id, wh_id in c.fetchall():
        if wh_id not in loc_by_wh:
            loc_by_wh[wh_id] = loc_id

    for wh_id, _ in warehouses:
        if wh_id not in loc_by_wh:
            loc_id = str(uuid.uuid4())
            if apply:
                c.execute(
                    "INSERT INTO nbin_locations (id, warehouse_id, code, name, is_default, is_active) VALUES (?, ?, 'MAIN', 'Main Location', 1, 1)",
                    (loc_id, wh_id),
                )
            loc_by_wh[wh_id] = loc_id

    # 2. Categories
    categories_needed = {p["category"] for p in products if p["category"]}
    c.execute("SELECT name, id FROM nbin_categories")
    existing_cats = dict(c.fetchall())
    cats_created = 0
    for cat_name in categories_needed:
        if cat_name not in existing_cats:
            cat_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"bishnoi.category.{cat_name}"))
            if apply:
                c.execute(
                    "INSERT INTO nbin_categories (id, name, is_active, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                    (cat_id, cat_name, now_str, now_str),
                )
            existing_cats[cat_name] = cat_id
            cats_created += 1

    # 3. Brands
    c.execute("SELECT name, id FROM nbin_brands")
    existing_brands = dict(c.fetchall())
    brands_created = 0
    for b_name in ["2MG", "Getmeds"]:
        if b_name not in existing_brands:
            b_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"bishnoi.brand.{b_name}"))
            if apply:
                c.execute(
                    "INSERT INTO nbin_brands (id, name, is_active, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                    (b_id, b_name, now_str, now_str),
                )
            existing_brands[b_name] = b_id
            brands_created += 1

    # 4. Units
    c.execute("SELECT code FROM nbin_units")
    existing_units = {r[0] for r in c.fetchall()}
    units_created = 0
    for p in products:
        uc = p["unit_code"]
        if uc not in existing_units:
            if apply:
                c.execute(
                    "INSERT INTO nbin_units (code, name, is_active) VALUES (?, ?, 1)",
                    (uc, p["unit_raw"].title()),
                )
            existing_units.add(uc)
            units_created += 1

    # 5. Products
    c.execute("SELECT sku, id FROM nbin_products")
    existing_prods_by_sku = dict(c.fetchall())
    c.execute("SELECT lower(name), id FROM nbin_products")
    existing_prods_by_name = dict(c.fetchall())

    c.execute("SELECT COALESCE(MAX(no), 40000000) FROM nbin_products")
    next_no = c.fetchone()[0] + 1

    prods_created = 0
    prods_updated = 0
    prod_id_map = {}

    for p in products:
        sku = p["sku"]
        name = p["name"]
        desc = f"{p['generic']} {p['strength']} {p['form']}".strip()
        cat_id = existing_cats.get(p["category"])
        brand_id = existing_brands.get(p["account"], existing_brands.get("Getmeds"))
        cost_p = p["dist_u_cents"]  # distributor price or 0
        sell_p = p["srp_u_cents"] or p["pat_u_cents"]
        tax_bp = p["tax_rate_bp"]
        u_code = p["unit_code"]

        attrs = json.dumps({
            "account": p["account"],
            "inventory": p["inventory_type"],
            "therapeutic_category": p["category"],
            "generic_name": p["generic"],
            "dosage_strength": p["strength"],
            "dosage_form": p["form"],
            "unit": p["unit_raw"],
            "pack_size": p["pack_size"],
            "count": p["count"],
            "shelf_life": p["shelf_life"],
            "doctor_price_unit": p["doc_u_cents"],
            "doctor_price_pack": p["doc_p_cents"],
            "doctor_deals": p["doc_deals"],
            "patient_price_unit": p["pat_u_cents"],
            "patient_price_pack": p["pat_p_cents"],
            "patient_discount_pct": p["pat_pct"],
            "patient_deals": p["pat_deals"],
            "distributor_price_unit": p["dist_u_cents"],
            "distributor_price_pack": p["dist_p_cents"],
            "distributor_deals": p["dist_deals"],
            "trade_price_unit": p["trade_u_cents"],
            "trade_price_pack": p["trade_p_cents"],
            "srp_unit": p["srp_u_cents"],
            "srp_pack": p["srp_p_cents"],
        }, ensure_ascii=False)

        # Match existing product by SKU or name
        prod_id = existing_prods_by_sku.get(sku)
        if not prod_id and name.lower() in existing_prods_by_name:
            prod_id = existing_prods_by_name[name.lower()]

        if prod_id:
            if apply:
                c.execute("""
                    UPDATE nbin_products
                    SET sku = ?, name = ?, description = ?, category_id = ?, brand_id = ?,
                        unit_code = ?, cost_price = ?, selling_price = ?, tax_rate_bp = ?,
                        tax_inclusive = 1, status = 'active', track_batches = 1, track_expiry = 1,
                        attributes = ?, updated_at = ?
                    WHERE id = ?
                """, (sku, name, desc, cat_id, brand_id, u_code, cost_p, sell_p, tax_bp, attrs, now_str, prod_id))
            prods_updated += 1
            prod_id_map[sku] = prod_id
        else:
            p_id = p["id"]
            if apply:
                c.execute("""
                    INSERT INTO nbin_products (
                        id, no, sku, name, description, category_id, brand_id, product_type,
                        unit_code, cost_price, selling_price, tax_rate_bp, tax_inclusive,
                        min_stock, reorder_point, reorder_qty, status, track_batches,
                        track_expiry, track_serials, attributes, created_at, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, 'stock',
                        ?, ?, ?, ?, 1,
                        0, 0, 0, 'active', 1,
                        1, 0, ?, ?, ?
                    )
                """, (p_id, next_no, sku, name, desc, cat_id, brand_id, u_code, cost_p, sell_p, tax_bp, attrs, now_str, now_str))
                next_no += 1
            prods_created += 1
            prod_id_map[sku] = p_id

    # Check if nbin_stock has on_hold column
    c.execute("PRAGMA table_info(nbin_stock)")
    stock_cols = {r[1] for r in c.fetchall()}
    has_on_hold = "on_hold" in stock_cols

    # 6. Stocks = 0 across all warehouses and locations (zero all existing stocks + create missing)
    if apply:
        if has_on_hold:
            c.execute("UPDATE nbin_stock SET on_hand = 0, damaged = 0, on_hold = 0, updated_at = ?", (now_str,))
        else:
            c.execute("UPDATE nbin_stock SET on_hand = 0, damaged = 0, updated_at = ?", (now_str,))

    c.execute("SELECT product_id, warehouse_id, location_id FROM nbin_stock")
    existing_stocks = {(r[0], r[1], r[2]) for r in c.fetchall()}

    stocks_created = 0
    stocks_zeroed = len(existing_stocks)

    for p in products:
        p_id = prod_id_map.get(p["sku"], p["id"])
        for wh_id, _ in warehouses:
            loc_id = loc_by_wh[wh_id]
            key = (p_id, wh_id, loc_id)
            if key not in existing_stocks:
                if apply:
                    stock_id = str(uuid.uuid4())
                    if has_on_hold:
                        c.execute("""
                            INSERT INTO nbin_stock (id, product_id, warehouse_id, location_id, on_hand, damaged, on_hold, updated_at)
                            VALUES (?, ?, ?, ?, 0, 0, 0, ?)
                        """, (stock_id, p_id, wh_id, loc_id, now_str))
                    else:
                        c.execute("""
                            INSERT INTO nbin_stock (id, product_id, warehouse_id, location_id, on_hand, damaged, updated_at)
                            VALUES (?, ?, ?, ?, 0, 0, ?)
                        """, (stock_id, p_id, wh_id, loc_id, now_str))
                stocks_created += 1
                existing_stocks.add(key)

    if apply:
        conn.commit()
    conn.close()

    return {
        "status": "applied" if apply else "dry_run",
        "products_created": prods_created,
        "products_updated": prods_updated,
        "stocks_created": stocks_created,
        "stocks_zeroed": stocks_zeroed,
        "categories_created": cats_created,
        "brands_created": brands_created,
        "units_created": units_created,
    }


def seed_crm_sqlite(db_path: Path | str, products: list[dict], apply: bool = False) -> dict:
    path = Path(db_path)
    if not path.exists():
        return {"status": "skipped", "reason": f"File does not exist: {path}"}

    if apply:
        make_backup(path)

    conn = sqlite3.connect(path)
    c = conn.cursor()
    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    # 1. Price Types
    c.execute("SELECT code FROM nbcm_price_types")
    existing_pts = {r[0] for r in c.fetchall()}
    needed_pts = [
        ("DOCTOR", "Doctor's Price", 1, "with_rx"),
        ("PATIENT", "Patient Price", 2, "always"),
        ("SRP", "Suggested Retail Price (SRP)", 3, "always"),
        ("TRADE", "Drugstore / Hospital Trade Price", 4, "always"),
        ("DISTRIBUTOR", "Distributor Price", 5, "always"),
    ]
    pts_created = 0
    for pt_code, pt_name, pt_sort, pt_rule in needed_pts:
        if pt_code not in existing_pts:
            if apply:
                c.execute("""
                    INSERT INTO nbcm_price_types (code, name, entry, rule, requires_notes, needs_approval, is_active, sort_order)
                    VALUES (?, ?, 'list', ?, 0, 0, 1, ?)
                """, (pt_code, pt_name, pt_rule, pt_sort))
            existing_pts.add(pt_code)
            pts_created += 1

    # 2. Products
    c.execute("SELECT code, id FROM nbcm_products")
    existing_crm_by_code = dict(c.fetchall())
    c.execute("SELECT lower(name), id FROM nbcm_products")
    existing_crm_by_name = dict(c.fetchall())

    prods_created = 0
    prods_updated = 0
    prices_set = 0

    for p in products:
        sku = p["sku"]
        name = p["name"]
        gen = p["generic"]
        st = p["strength"]
        form = p["form"]
        unit = p["unit_raw"]
        vat_cat = "vat" if p.get("is_vat") or p.get("tax_rate_bp", 0) > 0 else "exempt"
        inv_id = p["id"]

        extra_json = json.dumps({
            "account": p["account"],
            "inventory": p["inventory_type"],
            "category": p["category"],
            "pack_size": p["pack_size"],
            "count": p["count"],
            "shelf_life": p["shelf_life"],
            "doctor_deals": p["doc_deals"],
            "patient_deals": p["pat_deals"],
            "distributor_deals": p["dist_deals"],
            "distributor_price_unit": p["dist_u_cents"],
            "distributor_price_pack": p["dist_p_cents"],
            "trade_price_unit": p["trade_u_cents"],
            "trade_price_pack": p["trade_p_cents"],
            "srp_unit": p["srp_u_cents"],
            "srp_pack": p["srp_p_cents"],
        }, ensure_ascii=False)

        crm_id = existing_crm_by_code.get(sku)
        if not crm_id and name.lower() in existing_crm_by_name:
            crm_id = existing_crm_by_name[name.lower()]

        if crm_id:
            if apply:
                c.execute("""
                    UPDATE nbcm_products
                    SET code = ?, name = ?, generic_name = ?, strength = ?, form = ?, unit = ?,
                        is_active = 1, vat_category = ?, inventory_id = ?, extra = ?, updated_at = ?
                    WHERE id = ?
                """, (sku, name, gen, st, form, unit, vat_cat, inv_id, extra_json, now_str, crm_id))
            prods_updated += 1
        else:
            crm_id = str(uuid.uuid4())
            if apply:
                c.execute("""
                    INSERT INTO nbcm_products (id, code, name, generic_name, strength, form, unit, is_active, vat_category, inventory_id, extra, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """, (crm_id, sku, name, gen, st, form, unit, vat_cat, inv_id, extra_json, now_str, now_str))
            prods_created += 1

        # 3. Product Prices
        prices_to_set = [
            ("DOCTOR", p["doc_u_cents"] or p["doc_p_cents"]),
            ("PATIENT", p["pat_u_cents"] or p["pat_p_cents"]),
            ("DISTRIBUTOR", p["dist_u_cents"] or p["dist_p_cents"]),
            ("TRADE", p["trade_u_cents"] or p["trade_p_cents"]),
            ("SRP", p["srp_u_cents"] or p["srp_p_cents"]),
        ]
        for pt_code, amt in prices_to_set:
            if amt > 0:
                if apply:
                    c.execute("""
                        INSERT OR REPLACE INTO nbcm_product_prices (product_id, price_type_code, amount_centavos)
                        VALUES (?, ?, ?)
                    """, (crm_id, pt_code, amt))
                prices_set += 1

    if apply:
        conn.commit()
    conn.close()

    return {
        "status": "applied" if apply else "dry_run",
        "price_types_created": pts_created,
        "products_created": prods_created,
        "products_updated": prods_updated,
        "prices_set": prices_set,
    }


def seed_inventory_postgres(db_url: str, db_label: str, products: list[dict], apply: bool = False) -> dict:
    import psycopg
    from app.db import make_engine
    from app.migrate import upgrade

    # 0. Ensure schema migrations are up to date on this database
    engine = make_engine(db_url)
    upgrade(engine)
    engine.dispose()

    connect_url = re.sub(r"^postgresql\+[a-z0-9]+://", "postgresql://", db_url)
    connect_url = re.sub(r"^postgres://", "postgresql://", connect_url)
    now = datetime.now(UTC)
    with psycopg.connect(connect_url) as conn:
        with conn.cursor() as cur:
            # 1. Warehouses & Locations
            cur.execute("SELECT id, name FROM nbin_warehouses")
            warehouses = cur.fetchall()
            if not warehouses:
                wh_id = str(uuid.uuid4())
                if apply:
                    cur.execute(
                        "INSERT INTO nbin_warehouses (id, code, name, is_active, created_at, updated_at) VALUES (%s, 'MAIN', 'Main Warehouse', true, %s, %s)",
                        (wh_id, now, now),
                    )
                warehouses = [(wh_id, "Main Warehouse")]

            cur.execute("SELECT id, warehouse_id FROM nbin_locations")
            loc_by_wh = {}
            for loc_id, wh_id in cur.fetchall():
                if wh_id not in loc_by_wh:
                    loc_by_wh[wh_id] = loc_id

            for wh_id, _ in warehouses:
                if wh_id not in loc_by_wh:
                    loc_id = str(uuid.uuid4())
                    if apply:
                        cur.execute(
                            "INSERT INTO nbin_locations (id, warehouse_id, code, name, is_default, is_active) VALUES (%s, %s, 'MAIN', 'Main Location', true, true)",
                            (loc_id, wh_id),
                        )
                    loc_by_wh[wh_id] = loc_id

            # 2. Categories
            categories_needed = {p["category"] for p in products if p["category"]}
            cur.execute("SELECT name, id FROM nbin_categories")
            existing_cats = dict(cur.fetchall())
            for cat_name in categories_needed:
                if cat_name not in existing_cats:
                    cat_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"bishnoi.category.{cat_name}"))
                    if apply:
                        cur.execute(
                            "INSERT INTO nbin_categories (id, name, is_active, created_at, updated_at) VALUES (%s, %s, true, %s, %s)",
                            (cat_id, cat_name, now, now),
                        )
                    existing_cats[cat_name] = cat_id

            # 3. Brands
            cur.execute("SELECT name, id FROM nbin_brands")
            existing_brands = dict(cur.fetchall())
            for b_name in ["2MG", "Getmeds"]:
                if b_name not in existing_brands:
                    b_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"bishnoi.brand.{b_name}"))
                    if apply:
                        cur.execute(
                            "INSERT INTO nbin_brands (id, name, is_active, created_at, updated_at) VALUES (%s, %s, true, %s, %s)",
                            (b_id, b_name, now, now),
                        )
                    existing_brands[b_name] = b_id

            # 4. Units
            cur.execute("SELECT code FROM nbin_units")
            existing_units = {r[0] for r in cur.fetchall()}
            for p in products:
                uc = p["unit_code"]
                if uc not in existing_units:
                    if apply:
                        cur.execute(
                            "INSERT INTO nbin_units (code, name, is_active) VALUES (%s, %s, true)",
                            (uc, p["unit_raw"].title()),
                        )
                    existing_units.add(uc)

            # 5. Products
            cur.execute("SELECT sku, id FROM nbin_products")
            existing_prods_by_sku = dict(cur.fetchall())
            cur.execute("SELECT lower(name), id FROM nbin_products")
            existing_prods_by_name = dict(cur.fetchall())

            prod_created = 0
            prod_updated = 0
            prod_id_map = {}

            for p in products:
                sku = p["sku"]
                name = p["name"]
                desc = f"{p['generic']} {p['strength']} {p['form']}".strip()
                cat_id = existing_cats.get(p["category"])
                brand_id = existing_brands.get(p["account"], existing_brands.get("Getmeds"))
                cost_p = p["dist_u_cents"]
                sell_p = p["srp_u_cents"] or p["pat_u_cents"]
                tax_bp = p["tax_rate_bp"]
                u_code = p["unit_code"]

                attrs = json.dumps({
                    "account": p["account"],
                    "inventory": p["inventory_type"],
                    "therapeutic_category": p["category"],
                    "generic_name": p["generic"],
                    "dosage_strength": p["strength"],
                    "dosage_form": p["form"],
                    "pack_size": p["pack_size"],
                    "count": p["count"],
                    "shelf_life": p["shelf_life"],
                    "doctor_price_unit": p["doc_u_cents"],
                    "doctor_price_pack": p["doc_p_cents"],
                    "patient_price_unit": p["pat_u_cents"],
                    "patient_price_pack": p["pat_p_cents"],
                    "distributor_price_unit": p["dist_u_cents"],
                    "distributor_price_pack": p["dist_p_cents"],
                    "trade_price_unit": p["trade_u_cents"],
                    "trade_price_pack": p["trade_p_cents"],
                    "srp_unit": p["srp_u_cents"],
                    "srp_pack": p["srp_p_cents"],
                }, ensure_ascii=False)

                prod_id = existing_prods_by_sku.get(sku)
                if not prod_id and name.lower() in existing_prods_by_name:
                    prod_id = existing_prods_by_name[name.lower()]

                if prod_id:
                    if apply:
                        cur.execute("""
                            UPDATE nbin_products
                            SET sku = %s, name = %s, description = %s, category_id = %s, brand_id = %s,
                                unit_code = %s, cost_price = %s, selling_price = %s, tax_rate_bp = %s,
                                tax_inclusive = true, status = 'active', track_batches = true, track_expiry = true,
                                attributes = %s, updated_at = %s
                            WHERE id = %s
                        """, (sku, name, desc, cat_id, brand_id, u_code, cost_p, sell_p, tax_bp, attrs, now, prod_id))
                    prod_updated += 1
                    prod_id_map[sku] = prod_id
                else:
                    p_id = p["id"]
                    if apply:
                        cur.execute("""
                            INSERT INTO nbin_products (
                                id, sku, name, description, category_id, brand_id, product_type,
                                unit_code, cost_price, selling_price, tax_rate_bp, tax_inclusive,
                                min_stock, reorder_point, reorder_qty, status, track_batches,
                                track_expiry, track_serials, attributes, created_at, updated_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, 'stock',
                                %s, %s, %s, %s, true,
                                0, 0, 0, 'active', true,
                                true, false, %s, %s, %s
                            )
                        """, (p_id, sku, name, desc, cat_id, brand_id, u_code, cost_p, sell_p, tax_bp, attrs, now, now))
                    prod_created += 1
                    prod_id_map[sku] = p_id

            # 6. Stocks = 0
            cur.execute("SELECT product_id, warehouse_id, location_id FROM nbin_stock")
            existing_stocks = {(r[0], r[1], r[2]) for r in cur.fetchall()}
            stock_created = 0

            for p in products:
                p_id = prod_id_map.get(p["sku"], p["id"])
                for wh_id, _ in warehouses:
                    loc_id = loc_by_wh[wh_id]
                    key = (p_id, wh_id, loc_id)
                    if key not in existing_stocks:
                        if apply:
                            stock_id = str(uuid.uuid4())
                            cur.execute("""
                                INSERT INTO nbin_stock (id, product_id, warehouse_id, location_id, on_hand, damaged, on_hold, updated_at)
                                VALUES (%s, %s, %s, %s, 0, 0, 0, %s)
                            """, (stock_id, p_id, wh_id, loc_id, now))
                        stock_created += 1
                        existing_stocks.add(key)
                    else:
                        if apply:
                            cur.execute("""
                                UPDATE nbin_stock
                                SET on_hand = 0, damaged = 0, on_hold = 0, updated_at = %s
                                WHERE product_id = %s AND warehouse_id = %s AND location_id = %s
                            """, (now, p_id, wh_id, loc_id))

            if apply:
                conn.commit()

            return {
                "status": "applied" if apply else "dry_run",
                "products_created": prod_created,
                "products_updated": prod_updated,
                "stocks_created": stock_created,
            }


def main() -> int:
    _init_stdout()
    parser = argparse.ArgumentParser(description="Seed products, prices, and zero stocks from BEA Price List U0725.")
    parser.add_argument("--file", help="Optional Excel workbook path to re-parse from.")
    parser.add_argument("--sheet", default=DEFAULT_SHEET, help=f"Sheet name (default: {DEFAULT_SHEET})")
    parser.add_argument("--database-url", help="Target database URL (PostgreSQL or SQLite). If omitted, uses DATABASE_URL or local files.")
    parser.add_argument("--company", default="getmeds", help="The company's short name on Bishnoi One (default: getmeds)")
    parser.add_argument("--apply", action="store_true", help="Commit changes (default is dry run)")
    parser.add_argument("--all-databases", action="store_true", help="Sync to all targets: local SQLite, seed SQLite, and Neon")
    args = parser.parse_args()

    print("=" * 70)
    print("      BISHNOI ONE: PRODUCT SEED TOOL (BEA PRICE LIST U0725)     ")
    print("=" * 70)
    print(f"Mode       : {'APPLY (Saving changes)' if args.apply else 'DRY RUN (No changes saved)'}")
    print(f"Company    : {args.company}")
    print("=" * 70)

    if args.file and Path(args.file).exists():
        products = load_excel_products(args.file, args.sheet)
        print(f"\n[OK] Loaded {len(products)} products from Excel file '{args.file}'.")
    else:
        products = get_catalog_products()
        print(f"\n[OK] Loaded {len(products)} products from embedded BEA catalog.")

    target_db = args.database_url or os.environ.get("DATABASE_URL")
    if target_db:
        from app.tenants import clean, create_postgres_database, database_url
        from sqlalchemy.engine import make_url

        company = clean(args.company) or "getmeds"
        is_postgres = target_db.startswith(("postgres://", "postgresql://", "postgresql+"))

        if is_postgres:
            norm_url = re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", target_db)
            url_obj = make_url(norm_url)
            db_name = url_obj.database or ""
            # When pointing to root database without company suffix, target company tenant DB
            if not db_name.endswith(f"_{company}"):
                tenant_url = database_url(target_db, company)
                tenant_norm = re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", tenant_url)
                tenant_db_name = make_url(tenant_norm).database
                print(f"\n[Tenant] Base cluster DB '{db_name}' detected. Targeting company '{company}' DB: '{tenant_db_name}'")
                try:
                    create_postgres_database(target_db, tenant_db_name)
                except Exception as e:
                    print(f"[Tenant] Database check note: {e}")
                target_db = tenant_url

            label = target_db.split("@")[-1] if "@" in target_db else target_db
            print(f"\n--- Target Database ({label}) ---")
            res = seed_inventory_postgres(target_db, company, products, apply=args.apply)
            print(f"Result: {res}")
        else:
            sqlite_p = target_db.replace("sqlite:///", "")
            print(f"\n--- Target Database ({sqlite_p}) ---")
            res = seed_inventory_sqlite(sqlite_p, products, apply=args.apply)
            print(f"Result: {res}")

        if not args.all_databases:
            print("\n" + "=" * 70)
            if args.apply:
                print("          PRODUCT SEED COMPLETED AND APPLIED SUCCESSFULLY        ")
            else:
                print("    DRY RUN FINISHED. Run again with --apply to commit changes.   ")
            print("=" * 70)
            return 0

    # 1. Inventory SQLite: inventory-getmeds.db
    print("\n--- 1. Inventory SQLite (inventory-getmeds.db) ---")
    res_inv_getmeds = seed_inventory_sqlite(INV_GETMEDS_SQLITE, products, apply=args.apply)
    print(f"Result: {res_inv_getmeds}")

    # 2. CRM SQLite: crm-getmeds.db
    print("\n--- 2. CRM SQLite (crm-getmeds.db) ---")
    res_crm_getmeds = seed_crm_sqlite(CRM_GETMEDS_SQLITE, products, apply=args.apply)
    print(f"Result: {res_crm_getmeds}")

    if args.all_databases:
        # 3. Inventory SQLite: inventory.db (base)
        print("\n--- 3. Inventory SQLite Base (inventory.db) ---")
        res_inv_base = seed_inventory_sqlite(INV_BASE_SQLITE, products, apply=args.apply)
        print(f"Result: {res_inv_base}")

        # 4. CRM SQLite: crm.db (base)
        print("\n--- 4. CRM SQLite Base (crm.db) ---")
        res_crm_base = seed_crm_sqlite(CRM_BASE_SQLITE, products, apply=args.apply)
        print(f"Result: {res_crm_base}")

        # 5. Seed Directory (Desktop/bishnoi-one-seed)
        if SEED_INV_SQLITE.exists():
            print(f"\n--- 5. Seed Directory Inventory ({SEED_INV_SQLITE}) ---")
            res_seed_inv = seed_inventory_sqlite(SEED_INV_SQLITE, products, apply=args.apply)
            print(f"Result: {res_seed_inv}")
        if SEED_CRM_SQLITE.exists():
            print(f"\n--- 6. Seed Directory CRM ({SEED_CRM_SQLITE}) ---")
            res_seed_crm = seed_crm_sqlite(SEED_CRM_SQLITE, products, apply=args.apply)
            print(f"Result: {res_seed_crm}")

        # 7. Neon PostgreSQL if environment variables are set
        neon_inv = os.environ.get("INVENTORY_NEON_URL")
        if neon_inv:
            print("\n--- 7. Inventory Neon PostgreSQL ---")
            try:
                inv_db_url = neon_inv.replace("/neondb?", "/neondb_getmeds?")
                res_neon = seed_inventory_postgres(inv_db_url, "neondb_getmeds", products, apply=args.apply)
                print(f"Result: {res_neon}")
            except Exception as e:
                print(f"Neon error: {e}")

    print("\n" + "=" * 70)
    if args.apply:
        print("          PRODUCT SEED COMPLETED AND APPLIED SUCCESSFULLY        ")
    else:
        print("    DRY RUN FINISHED. Run again with --apply to commit changes.   ")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
