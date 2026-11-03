"""Unit tests for the product seed tool (BEA Price List U0725)."""

import sqlite3
from pathlib import Path
import pytest

from app.tools.seed_products import (
    DEFAULT_EXCEL_PATH,
    DEFAULT_SHEET,
    clean_sku,
    load_excel_products,
    seed_crm_sqlite,
    seed_inventory_sqlite,
    to_centavos,
)


def test_clean_sku():
    assert clean_sku("AmloGet 5", "Amlodipine", "5 mg") == "AMLOGET-5-MG"
    assert clean_sku("MidaGet", "Midazolam [REGULATED]", "150 mg/3 ml") == "MIDAGET-150-MG-3-ML"
    assert clean_sku("Sondelbay", "Teriparatide [COLD CHAIN]", "20 mcg/80 mcL (600 mcg/2.4 ml)") == "SONDELBAY-20-MCG-80-MCL"
    # Multi-size injectables include total dose in SKU
    assert clean_sku("CarboGet", "Carboplatin", "10 mg/ml (150 mg/15 ml)") == "CARBOGET-150MG-10-MG-ML"
    assert clean_sku("CarboGet", "Carboplatin", "10 mg/ml (450 mg/45 ml)") == "CARBOGET-450MG-10-MG-ML"
    assert clean_sku("OxaliGet", "Oxaliplatin", "2 mg/ml (50 mg/25 ml)") == "OXALIGET-50MG-2-MG-ML"
    assert clean_sku("OxaliGet", "Oxaliplatin", "2 mg/ml (100 mg/50 ml)") == "OXALIGET-100MG-2-MG-ML"
    # Supplies without brand
    assert clean_sku("Getmeds", "Blood Transfusion Set", "-") == "GETMEDS-BLOOD-TRANSFUSION-SET"
    assert clean_sku("Getmeds", "Intravenous Cannula Set", "G24") == "GETMEDS-G24"


def test_to_centavos():
    assert to_centavos(120.0) == 12000
    assert to_centavos(1.17) == 117
    assert to_centavos("2,500.50") == 250050
    assert to_centavos(None) == 0
    assert to_centavos("") == 0


def test_load_excel_products_from_file():
    if not Path(DEFAULT_EXCEL_PATH).exists():
        pytest.skip(f"Excel file not found at {DEFAULT_EXCEL_PATH}")

    products = load_excel_products(DEFAULT_EXCEL_PATH, DEFAULT_SHEET)
    assert len(products) == 64

    # Verify first product (AmiGet)
    p0 = products[0]
    assert p0["name"] == "AmiGet"
    assert p0["generic"] == "Amikacin"
    assert p0["tax_rate_bp"] == 1200
    assert p0["is_vat"] is True
    assert p0["srp_u_cents"] == 12000
    assert p0["doc_u_cents"] == 3800
    assert p0["dist_u_cents"] == 3000

    # Verify VAT-exempt product (AmloGet 5)
    p1 = products[1]
    assert p1["name"] == "AmloGet 5"
    assert p1["tax_rate_bp"] == 0
    assert p1["is_vat"] is False
    assert p1["srp_u_cents"] == 300
    assert p1["doc_u_cents"] == 110


def test_seed_inventory_and_crm_idempotent(tmp_path):
    inv_db = tmp_path / "inventory.db"
    crm_db = tmp_path / "crm.db"

    # Set up minimal inventory schema
    with sqlite3.connect(inv_db) as conn:
        conn.executescript("""
            CREATE TABLE nbin_warehouses (id TEXT PRIMARY KEY, code TEXT, name TEXT, is_active INTEGER, created_at TEXT, updated_at TEXT);
            CREATE TABLE nbin_locations (id TEXT PRIMARY KEY, warehouse_id TEXT, code TEXT, name TEXT, is_default INTEGER, is_active INTEGER);
            CREATE TABLE nbin_categories (id TEXT PRIMARY KEY, name TEXT UNIQUE, is_active INTEGER, created_at TEXT, updated_at TEXT);
            CREATE TABLE nbin_brands (id TEXT PRIMARY KEY, name TEXT UNIQUE, is_active INTEGER, created_at TEXT, updated_at TEXT);
            CREATE TABLE nbin_units (code TEXT PRIMARY KEY, name TEXT, is_active INTEGER);
            CREATE TABLE nbin_products (
                id TEXT PRIMARY KEY, no INTEGER, sku TEXT UNIQUE, name TEXT, description TEXT,
                category_id TEXT, brand_id TEXT, product_type TEXT, unit_code TEXT,
                cost_price INTEGER, selling_price INTEGER, tax_rate_bp INTEGER, tax_inclusive INTEGER,
                min_stock INTEGER, reorder_point INTEGER, reorder_qty INTEGER, status TEXT,
                track_batches INTEGER, track_expiry INTEGER, track_serials INTEGER,
                attributes TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE nbin_stock (
                id TEXT PRIMARY KEY, product_id TEXT, warehouse_id TEXT, location_id TEXT,
                on_hand INTEGER, damaged INTEGER, on_hold INTEGER, updated_at TEXT
            );
            INSERT INTO nbin_warehouses (id, code, name, is_active) VALUES ('wh-1', 'MAIN', 'Main WH', 1);
            INSERT INTO nbin_locations (id, warehouse_id, code, name, is_default, is_active) VALUES ('loc-1', 'wh-1', 'MAIN', 'Main Loc', 1, 1);
        """)

    # Set up minimal CRM schema
    with sqlite3.connect(crm_db) as conn:
        conn.executescript("""
            CREATE TABLE nbcm_price_types (code TEXT PRIMARY KEY, name TEXT, entry TEXT, rule TEXT, requires_notes INTEGER, needs_approval INTEGER, is_active INTEGER, sort_order INTEGER);
            CREATE TABLE nbcm_products (
                id TEXT PRIMARY KEY, code TEXT UNIQUE, name TEXT, generic_name TEXT, strength TEXT,
                form TEXT, unit TEXT, is_active INTEGER, vat_category TEXT, inventory_id TEXT,
                extra TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE nbcm_product_prices (
                product_id TEXT, price_type_code TEXT, amount_centavos INTEGER,
                PRIMARY KEY (product_id, price_type_code)
            );
        """)

    sample_products = [
        {
            "id": "prod-1",
            "sku": "AMIGET-250-MG-ML",
            "name": "AmiGet",
            "account": "2MG",
            "inventory_type": "INHOUSE",
            "category": "Antibacterial",
            "generic": "Amikacin",
            "strength": "250 mg/ml (500 mg/2 ml)",
            "form": "Sol'n for Inj.",
            "unit_raw": "Vial",
            "unit_code": "vial",
            "pack_size": "Box of 1's",
            "count": 1,
            "shelf_life": "36 months",
            "tax": "VAT",
            "is_vat": True,
            "tax_rate_bp": 1200,
            "doc_u_cents": 3800,
            "doc_p_cents": 3800,
            "doc_deals": None,
            "pat_u_cents": 0,
            "pat_p_cents": 0,
            "pat_pct": None,
            "pat_deals": None,
            "dist_u_cents": 3000,
            "dist_p_cents": 3000,
            "dist_deals": None,
            "trade_u_cents": 6000,
            "trade_p_cents": 6000,
            "srp_u_cents": 12000,
            "srp_p_cents": 12000,
        }
    ]

    # First run (apply)
    inv_res = seed_inventory_sqlite(inv_db, sample_products, apply=True)
    crm_res = seed_crm_sqlite(crm_db, sample_products, apply=True)

    assert inv_res["products_created"] == 1
    assert inv_res["stocks_created"] == 1
    assert crm_res["products_created"] == 1
    assert crm_res["prices_set"] == 4  # DOCTOR, DISTRIBUTOR, TRADE, SRP (PATIENT is 0)

    # Verify inventory stock is 0
    with sqlite3.connect(inv_db) as conn:
        c = conn.cursor()
        c.execute("SELECT on_hand, damaged, on_hold FROM nbin_stock WHERE product_id = 'prod-1'")
        stock = c.fetchone()
        assert stock == (0, 0, 0)
        c.execute("SELECT selling_price, tax_rate_bp, tax_inclusive FROM nbin_products WHERE id = 'prod-1'")
        prod = c.fetchone()
        assert prod == (12000, 1200, 1)

    # Second run (apply) - should update, not create duplicate
    inv_res2 = seed_inventory_sqlite(inv_db, sample_products, apply=True)
    crm_res2 = seed_crm_sqlite(crm_db, sample_products, apply=True)

    assert inv_res2["products_created"] == 0
    assert inv_res2["products_updated"] == 1
    assert inv_res2["stocks_created"] == 0
    assert inv_res2["stocks_zeroed"] == 1
    assert crm_res2["products_created"] == 0
    assert crm_res2["products_updated"] == 1
