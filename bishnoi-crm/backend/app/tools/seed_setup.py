"""Adds a CRM's set-up from another copy of it, following the target (2026-11-03: "we follow the live").

The live CRM is the standard: its teams, roles and everything already set up stay exactly as they are. From a
copy (this computer's, or Neon's) this adds only what the target lacks, by name or code, and says what it left out:

  customer types, price types, issuers, products with their prices, bundles, promos, attention rules,
  KPIs, scorecards, quotation templates (with their files), form sections and fields

Teams and roles are matched by name (the platform owns them, so their ids differ): a customer type limited to the
copy's "STC" is limited to the target's ONCO CARE. A team or role the target doesn't have is left out of the list; a row
that can only mean that team or role (an attention rule, a KPI for roles it doesn't have) is skipped and named. Never
copied: people, roles, teams, targets, deal stages, settings, anything the work made (customers, quotes, visits), and
the copy's test rows ("Sample ...").

    1. uv run python -m app.tools.seed_setup export --from sqlite:///.data/crm-getmeds.db --out seed.json
    2. on the server:  uv run python -m app.tools.seed_setup apply --company <slug> --file seed.json [--apply]

`apply` only says what it would do unless --apply is given.
"""

import argparse
import base64
import json
import re
import sys
from datetime import date, datetime
from typing import Any

from sqlalchemy import DateTime, LargeBinary, select
from sqlalchemy import Date as SqlDate
from sqlalchemy.orm import Session

from app.config import get_settings
from app import models  # noqa: F401  (puts every table into Base.metadata)
from app.db import Base, make_engine
from app.tenants import database_url

TOOL = "set-up seed tool"
# Written to the file in this order; added in this order, so what a row points at is there first.
TABLES = ["customer_types", "price_types", "issuers", "products", "product_prices", "bundles", "promos", "attention_rules", "kpis", "scorecards",
          "stored_files", "quote_templates", "form_sections", "form_fields"]
# The copy's team names, as the live chart names them (decided 2026-11-03: the live chart is the standard).
ALIASES = {
    "stc": "onco care", "uro": "uro & oncology", "b&b": "blood & bone care", "b2c": "b2c", "md telesales": "md telesales", "hos": "hos",
    "telesales": "md telesales - anesthesia", "field ncr 1": "ncr 1", "field ncr 2": "ncr 2", "field north and central luzon": "north & central luzon",
    "field south luzon": "south luzon", "field visayas": "visayas", "field mindanao": "mindanao", "government account": "government account",
    "patient assistance program": "patient assistance program - pap", "bid": "government bidding", "clidp": "clidp",
    "b2b nbd": "new business development", "b2b crr": "client retention & reorder", "b2b": "b2b telesales",
    "prescription business": "prescription business",
}
TEAM_LISTS = {"customer_types": ("only_teams", "except_teams"), "form_fields": ("only_teams", "except_teams"), "bundles": ("team_ids",),
              "promos": ("team_ids",), "scorecards": ("teams",)}
ROLE_LISTS = {"kpis": ("roles",), "scorecards": ("roles",)}


def norm(name: str | None) -> str:
    return re.sub(r"\s+", " ", (name or "")).strip().lower()


def table(name: str):
    return Base.metadata.tables[f"nbcm_{name}"]


def dump(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"$dt": value.isoformat()}
    if isinstance(value, date):
        return {"$d": value.isoformat()}
    if isinstance(value, bytes):
        return {"$b": base64.b64encode(value).decode()}
    return value


def load(column, value: Any) -> Any:
    if isinstance(value, dict) and len(value) == 1:
        if "$dt" in value:
            return datetime.fromisoformat(value["$dt"])
        if "$d" in value:
            return date.fromisoformat(value["$d"])
        if "$b" in value:
            return base64.b64decode(value["$b"])
    return value


def export(url: str, out: str) -> int:
    engine = make_engine(url)
    data: dict[str, Any] = {"tables": {}}
    with Session(engine) as db:
        data["teams"] = {t.id: t.name for t in db.execute(select(table("teams").c.id, table("teams").c.name))}
        data["roles"] = {r.id: r.name for r in db.execute(select(table("roles").c.id, table("roles").c.name))}
        for name in TABLES:
            t = table(name)
            data["tables"][name] = [{c.name: dump(v) for c, v in zip(t.columns, row)} for row in db.execute(select(t))]
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{out}: " + ", ".join(f"{len(rows)} {name}" for name, rows in data["tables"].items()))
    return 0


def apply(db: Session, data: dict) -> tuple[dict[str, dict[str, int]], list[str]]:
    said: dict[str, dict[str, int]] = {}
    notes: list[str] = []
    live_teams = {norm(r.name): r.id for r in db.execute(select(table("teams").c.id, table("teams").c.name))}
    live_roles = {norm(r.name): r.id for r in db.execute(select(table("roles").c.id, table("roles").c.name))}
    team_map = {tid: live_teams.get(ALIASES.get(norm(name), norm(name))) for tid, name in data["teams"].items()}
    role_map = {rid: live_roles.get(norm(name)) for rid, name in data["roles"].items()}
    team_name, role_name = data["teams"], data["roles"]
    product_map: dict[str, str] = {}
    sections: dict[str, str] = {}

    def count(name: str, what: str) -> None:
        said.setdefault(name, {}).setdefault(what, 0)
        said[name][what] += 1

    def remap(ids: Any, mapping: dict, names: dict, label: str) -> tuple[list, list]:
        kept, lost = [], []
        for i in ids or []:
            (kept if mapping.get(i) else lost).append(mapping.get(i) or names.get(i, i))
        return kept, lost

    def insert(name: str, row: dict) -> None:
        t = table(name)
        db.execute(t.insert().values({c.name: load(c, row[c.name]) for c in t.columns if c.name in row}))
        count(name, "added")

    def have(tbl: str, **keys) -> bool:
        t = table(tbl)
        return db.execute(select(t).where(*(t.c[k] == v for k, v in keys.items())).limit(1)).first() is not None

    def named(tbl: str, row: dict) -> bool:
        """The target has it already, under this code or this name (it keeps its own: the live one's names are the standard)."""
        t = table(tbl)
        names = db.execute(select(*(t.c[k] for k in ("code", "name") if k in t.c))).all()
        mine = {norm(str(v)) for v in (row.get("code"), row.get("name")) if v}
        return any(norm(str(v)) in mine for r in names for v in r)

    for name in TABLES:
        for src in data["tables"].get(name, []):
            row = dict(src)
            label = row.get("name") or row.get("code") or row.get("title") or row.get("key") or row.get("product_id", "")
            if str(label).lower().startswith("sample"):
                count(name, "test row left out")
                continue
            skip = False
            for field in TEAM_LISTS.get(name, ()):
                kept, lost = remap(row.get(field), team_map, team_name, "team")
                # A list that was limited to teams the target hasn't would become "everyone": a limit lost is a row skipped.
                if row.get(field) and not kept and field in ("only_teams", "teams"):
                    notes.append(f"{name} {label}: none of its teams ({', '.join(map(str, lost))}) are on the live chart")
                    skip = True
                elif lost:
                    notes.append(f"{name} {label}: {', '.join(map(str, lost))} not on the live chart, left out of its {field}")
                row[field] = kept
            for field in ROLE_LISTS.get(name, ()):
                kept, lost = remap(row.get(field), role_map, role_name, "role")
                if row.get(field) and not kept:
                    notes.append(f"{name} {label}: none of its roles ({', '.join(map(str, lost))}) are on live")
                    skip = True
                elif lost:
                    notes.append(f"{name} {label}: {', '.join(map(str, lost))} not on live, left out of its roles")
                row[field] = kept
            if skip:
                count(name, "skipped")
                continue

            if name == "customer_types":
                t = table(name)
                found = next((r for r in db.execute(select(t)).mappings() if norm(r["name"]) == norm(row["name"]) or r["code"] == row["code"]), None)
                if found is None:
                    insert(name, row)
                elif not found["only_teams"] and not found["except_teams"] and (row["only_teams"] or row["except_teams"]):
                    # Live has the type with no limits (made by hand): the copy's limits, matched to live's teams, are added; any it already has stay.
                    db.execute(t.update().where(t.c.code == found["code"]).values(only_teams=row["only_teams"], except_teams=row["except_teams"]))
                    count(name, "limited to their teams")
                else:
                    count(name, "already there")
            elif name in ("price_types", "issuers"):
                (count(name, "already there") if named(name, row) else insert(name, row))
            elif name == "products":
                t = table(name)
                found = db.execute(select(t.c.id).where(t.c.code == row["code"])).scalar()
                product_map[row["id"]] = found or row["id"]
                if found:
                    count(name, "already there")
                else:
                    row.pop("no", None)
                    row["inventory_id"] = None
                    insert(name, row)
            elif name == "product_prices":
                pid = product_map.get(row["product_id"])
                if pid is None:
                    count(name, "skipped")
                elif have(name, product_id=pid, price_type_code=row["price_type_code"]):
                    count(name, "already there")
                else:
                    row.update(product_id=pid, submitted_by_id=None, approved_by_id=None)
                    insert(name, row)
            elif name in ("bundles", "promos"):
                if have(name, name=row["name"]):
                    count(name, "already there")
                else:
                    if name == "bundles":
                        row["items"] = [{**i, "productId": product_map.get(i.get("productId"), i.get("productId"))} for i in row.get("items") or []]
                    else:
                        row["product_ids"] = [product_map.get(i, i) for i in row.get("product_ids") or []]
                    insert(name, row)
            elif name == "attention_rules":
                tid = team_map.get(row["team_id"]) if row.get("team_id") else None
                if row.get("team_id") and not tid:
                    notes.append(f"attention rule for {team_name.get(row['team_id'], '?')}: not on the live chart")
                    count(name, "skipped")
                elif have(name, team_id=tid):
                    count(name, "already there")
                else:
                    insert(name, {**row, "team_id": tid})
            elif name in ("kpis", "scorecards"):
                (count(name, "already there") if named(name, row) else insert(name, row))
            elif name == "stored_files":
                (count(name, "already there") if have(name, ref=row["ref"]) else insert(name, row))
            elif name == "quote_templates":
                tid = team_map.get(row["team_id"]) if row.get("team_id") else None
                if row.get("team_id") and not tid:
                    notes.append(f"quote template {label}: its team is not on the live chart")
                    count(name, "skipped")
                elif have(name, name=row["name"]):
                    count(name, "already there")
                else:
                    insert(name, {**row, "team_id": tid})
            elif name == "form_sections":
                t = table(name)
                found = db.execute(select(t.c.id).where(t.c.entity == row["entity"], t.c.title == row["title"])).scalar()
                sections[row["id"]] = found or row["id"]
                if found:
                    count(name, "already there")
                else:
                    insert(name, row)
            elif name == "form_fields":
                if have(name, entity=row["entity"], key=row["key"]):
                    count(name, "already there")
                else:
                    row["section_id"] = sections.get(row.get("section_id"), row.get("section_id"))
                    insert(name, row)
    return said, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Add a CRM's set-up from another copy, following the target.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="write the copy's set-up to a file")
    e.add_argument("--from", dest="source", required=True, help="the copy's database address")
    e.add_argument("--out", required=True)
    a = sub.add_parser("apply", help="add what the target lacks")
    a.add_argument("--company", required=True, help="the company's short name, e.g. getmeds-philippines-inc")
    a.add_argument("--file", required=True)
    a.add_argument("--platform-db", help="the CRM's database (default: DATABASE_URL, with the company)")
    a.add_argument("--apply", action="store_true", help="save it (without this, only says what it would do)")
    args = parser.parse_args()
    if args.cmd == "export":
        return export(args.source, args.out)

    data = json.load(open(args.file, encoding="utf-8"))
    engine = make_engine(args.platform_db or database_url(get_settings().database_url, args.company))
    with Session(engine) as db:
        said, notes = apply(db, data)
        for name, parts in said.items():
            print(f"{name:18} " + ", ".join(f"{n} {what}" for what, n in parts.items()))
        for n in notes:
            print(f"  - {n}")
        if args.apply:
            from app.audit import audit

            audit(db, TOOL, "setup.seeded", fields=[f"{p.get('added', 0)} {n}" for n, p in said.items() if p.get("added")])
            db.commit()
            print("Saved.")
        else:
            db.rollback()
            print("Dry run, nothing saved. Run again with --apply to save it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
