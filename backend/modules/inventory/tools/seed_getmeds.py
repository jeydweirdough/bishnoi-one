"""Brings Getmeds' Inventory set-up into a company's database (2026-11-19), from the data kept beside this file
(getmeds_setup_data.json, taken from the office server seed: live Neon's vendors and warehouses).

  vendors     143 (codes = Zoho numbers, 5 in USD)
  warehouses  11, each with its locations
  categories, brands, units, couriers

Adds only what isn't there yet (vendors and warehouses by code, the rest by name or code); nothing already there is
changed. Products and prices come from seed_products (BEA price list). Nothing is saved without --apply.

    uv run python -m modules.inventory.tools.seed_getmeds --company getmeds-philippines-inc [--apply]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, select

from modules.inventory.audit import audit
from modules.inventory.config import get_settings
from modules.inventory.db import make_engine, make_sessions
from modules.inventory.migrate import upgrade
from modules.inventory.models import Brand, Category, Courier, Location, Supplier, Unit, Warehouse
from modules.inventory.tenants import create_postgres_database, database_url

DATA = Path(__file__).with_name("getmeds_setup_data.json")
WHO = "Getmeds set-up seed"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--company", required=True, help="the company's short name, e.g. getmeds-philippines-inc")
    p.add_argument("--to", help="the app's database (DATABASE_URL when not given)")
    p.add_argument("--apply", action="store_true", help="save it (without this, only says what it would do)")
    args = p.parse_args()

    data = json.loads(DATA.read_text(encoding="utf-8"))
    base = args.to or get_settings().database_url
    url = database_url(base, args.company)
    if not url.startswith("sqlite"):
        create_postgres_database(base, url.rsplit("/", 1)[-1].split("?")[0])
    engine = make_engine(url)
    upgrade(engine)
    added: dict[str, int] = {}

    def count(kind: str) -> None:
        added[kind] = added.get(kind, 0) + 1

    with make_sessions(engine)() as db:
        for u in data["units"]:
            if db.get(Unit, u["code"]) is None:
                db.add(Unit(**u))
                count("units")
        for b in data["brands"]:
            if db.scalar(select(Brand).where(func.lower(Brand.name) == b["name"].lower())) is None:
                db.add(Brand(**b))
                count("brands")
        db.flush()

        by_name = {c.name: c for c in db.scalars(select(Category))}
        pending = list(data["categories"])
        while pending:  # parents before children
            later = []
            for c in pending:
                if c["name"] in by_name:
                    continue
                if c["parent"] and c["parent"] not in by_name:
                    later.append(c)
                    continue
                row = Category(name=c["name"], description=c["description"], is_active=c["is_active"],
                               parent_id=by_name[c["parent"]].id if c["parent"] else None)
                db.add(row)
                db.flush()
                by_name[row.name] = row
                count("categories")
            if len(later) == len(pending):
                for c in later:
                    print(f"  left out category {c['name']}: its parent {c['parent']} isn't there")
                break
            pending = later

        for c in data["couriers"]:
            if db.scalar(select(Courier).where(func.lower(Courier.code) == c["code"].lower())) is None:
                db.add(Courier(**c))
                count("couriers")

        for s in data["suppliers"]:
            if db.scalar(select(Supplier).where(func.lower(Supplier.code) == s["code"].lower())) is None:
                row = Supplier(**s)
                db.add(row)
                db.flush()
                audit(db, WHO, "supplier.created", target=row.name, target_type="supplier", target_id=row.id)
                count("vendors")
        db.flush()

        vendors = {v.code.upper(): v.id for v in db.scalars(select(Supplier))}
        for w in data["warehouses"]:
            row = db.scalar(select(Warehouse).where(func.lower(Warehouse.code) == w["code"].lower()))
            if row is not None:
                continue
            row = Warehouse(**w)
            db.add(row)
            db.flush()
            audit(db, WHO, "warehouse.created", target=row.name, target_type="warehouse", target_id=row.id)
            count("warehouses")
            places = [x for x in data["locations"] if x["warehouse"] == w["code"]] or [
                {"code": "MAIN", "name": "Main area", "is_default": True, "is_active": True, "consignment_supplier": None}]
            for x in places:
                db.add(Location(warehouse_id=row.id, code=x["code"], name=x["name"], is_default=x["is_default"],
                                is_active=x["is_active"],
                                consignment_supplier_id=vendors.get((x["consignment_supplier"] or "").upper())))
                count("locations")

        where = url.split("@")[-1].split("?")[0]
        print(f"{where}: added " + (", ".join(f"{n} {k}" for k, n in added.items()) or "nothing (all there already)"))
        if args.apply:
            db.commit()
            print("Saved.")
        else:
            db.rollback()
            print("Dry run: nothing saved. Add --apply to save.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
