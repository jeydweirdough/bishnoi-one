"""Imports: products (with their prices) and people's accounts, from a
spreadsheet (.xlsx or .csv).

1. /imports/{kind}/read: the file is read, never kept. What comes back is its
   headers, its rows, the fields they can go into, and a first guess at which
   column goes where (from the headers' names).
2. /imports/{kind}: the rows and the mapping the person settled on. With
   dryRun it only checks, row by row, and saves nothing. Without it, the rows
   that pass are saved and the ones that don't are listed with why.

An existing product is matched by its code, an existing person by their email:
those are updated, not added twice.

Products need products.create and products.edit; people need admin.users.
"""

import csv
import io
import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import Access, CurrentAccess, keep_an_administrator
from app.api import EMAIL, Api
from app.audit import audit
from app.deps import DB, CurrentUser
from app.extra import _value, fields_for
from app.models import PriceType, Product, ProductPrice, Role, Team, User
from app.permissions import SALESPERSON
from app.security import check_password_rules, hash_password

router = APIRouter(prefix="/imports", tags=["imports"])

Kind = Literal["products", "people"]
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000


def allowed(access: Access, kind: str) -> None:
    need = ("products.create", "products.edit") if kind == "products" else ("admin.users",)
    for permission in need:
        access.require(permission)


def normal(text: str) -> str:
    """A header or a name, as compared: lower case, letters and digits only."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


# --- the fields a row can go into ------------------------------------------------------------


def fields_of(db: Session, kind: str) -> list[dict]:
    """Each field: its key, its label, whether it's required, and other names a
    header might call it."""
    if kind == "people":
        return [
            {"key": "email", "label": "Email", "required": True, "aliases": ["email", "emailaddress", "workemail", "mail"]},
            {"key": "fullName", "label": "Full name (needed for new people)", "required": False, "aliases": ["name", "fullname", "employee", "employeename", "person"]},
            {"key": "role", "label": "Role", "required": False, "aliases": ["role", "position", "access"]},
            {"key": "team", "label": "Team", "required": False, "aliases": ["team", "division", "group", "department"]},
        ]
    out = [
        {"key": "code", "label": "Code", "required": True, "aliases": ["code", "sku", "itemcode", "productcode", "item"]},
        {"key": "name", "label": "Name (needed for new products)", "required": False, "aliases": ["name", "productname", "brand", "brandname", "description", "itemname"]},
        {"key": "genericName", "label": "Generic name", "required": False, "aliases": ["generic", "genericname", "molecule"]},
        {"key": "strength", "label": "Strength", "required": False, "aliases": ["strength", "dosage", "dose"]},
        {"key": "form", "label": "Form", "required": False, "aliases": ["form", "dosageform"]},
        {"key": "unit", "label": "Sold by (needed for new products)", "required": False, "aliases": ["unit", "uom", "soldby", "pack", "packsize"]},
        {"key": "isActive", "label": "On sale", "required": False, "aliases": ["active", "onsale", "status", "isactive"]},
    ]
    for t in db.scalars(select(PriceType).where(PriceType.entry == "list").order_by(PriceType.sort_order, PriceType.name)):
        out.append({"key": f"price:{t.code}", "label": f"Price: {t.name}", "required": False, "aliases": [t.name, t.code, f"{t.name}price", f"{t.code}price"]})
    for f in fields_for(db, "product", added_only=True, shown_only=True):
        out.append({"key": f"extra:{f.key}", "label": f.label, "required": False, "aliases": [f.label, f.key.removeprefix("x_")]})
    return out


def guess(fields: list[dict], headers: list[str]) -> dict[str, int | None]:
    """Which column each field most likely is, by its header's name."""
    taken: set[int] = set()
    out: dict[str, int | None] = {}
    for f in fields:
        names = {normal(a) for a in [f["label"], f["key"], *f["aliases"]]}
        hit = next((i for i, h in enumerate(headers) if i not in taken and normal(h) in names), None)
        if hit is not None:
            taken.add(hit)
        out[f["key"]] = hit
    return out


# --- reading the file ------------------------------------------------------------------------


def cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_rows(name: str, data: bytes) -> list[list[str]]:
    if name.lower().endswith(".csv"):
        text = data.decode("utf-8-sig", errors="replace")
        return [[c.strip() for c in row] for row in csv.reader(io.StringIO(text))]
    if name.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        try:
            book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That file couldn't be read as an Excel workbook.") from None
        sheet = book.worksheets[0]
        return [[cell(v) for v in row] for row in sheet.iter_rows(values_only=True)]
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use an Excel file (.xlsx) or a CSV file (.csv).")


@router.post("/{kind}/read")
async def read_file(access: CurrentAccess, db: DB, kind: Kind, file: Annotated[UploadFile, File()]) -> dict:
    allowed(access, kind)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The file is over 5 MB. Split it, or take out what isn't needed.")
    rows = [r for r in read_rows(file.filename or "", data) if any(c for c in r)]
    if not rows:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The file is empty.")
    headers, body = rows[0], rows[1:]
    if len(body) > MAX_ROWS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"The file has {len(body)} rows; import at most {MAX_ROWS} at a time.")
    width = max(len(r) for r in rows)
    headers = [h or f"Column {i + 1}" for i, h in enumerate(headers + [""] * (width - len(headers)))]
    fields = fields_of(db, kind)
    return {
        "fileName": file.filename,
        "headers": headers,
        "rows": [r + [""] * (width - len(r)) for r in body],
        "fields": [{k: f[k] for k in ("key", "label", "required")} for f in fields],
        "mapping": guess(fields, headers),
    }


# --- importing -------------------------------------------------------------------------------


class ImportIn(Api):
    # field key -> column index (None: not in the file)
    mapping: dict[str, int | None]
    rows: list[list[str]] = Field(max_length=MAX_ROWS)
    dry_run: bool = True
    # People: the first password for accounts made now; and whether to make teams not there yet.
    password: str | None = Field(None, max_length=256)
    make_teams: bool = True


def money(text: str) -> int:
    """An amount as written in a spreadsheet ("1,250.00", "₱ 250"), in centavos."""
    clean = re.sub(r"[^0-9.\-]", "", text)
    if not clean:
        raise ValueError(f"{text!r} isn't an amount.")
    try:
        value = round(float(clean) * 100)
    except ValueError:
        raise ValueError(f"{text!r} isn't an amount.") from None
    if value <= 0:
        raise ValueError("Prices are above zero.")
    return value


def yes_no(text: str) -> bool:
    t = normal(text)
    if t in ("yes", "y", "true", "1", "active", "onsale", "on"):
        return True
    if t in ("no", "n", "false", "0", "inactive", "off", "discontinued"):
        return False
    raise ValueError(f"{text!r}: write yes or no.")


def import_products(db: Session, me: User, body: ImportIn, get) -> tuple[int, int, list[dict]]:
    added = {f.key: f for f in fields_for(db, "product", added_only=True, shown_only=True)}
    existing = {p.code.upper(): p for p in db.scalars(select(Product))}
    seen: set[str] = set()
    made = changed = 0
    problems: list[dict] = []
    for n, row in enumerate(body.rows, start=2):
        if not any(c.strip() for c in row):
            continue
        v = lambda key: get(row, key)  # noqa: E731
        mapped = lambda key: body.mapping.get(key) is not None and bool(v(key))  # noqa: E731
        try:
            # Everything is read and checked first; only a row that passes changes anything.
            code = v("code").upper()
            if not code:
                raise ValueError("No code.")
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9_.\-]*", code):
                raise ValueError(f"Code {code}: letters, numbers, dots, dashes or underscores only.")
            if code in seen:
                raise ValueError(f"Code {code} is on another row of this file too.")
            product = existing.get(code)
            if product is None:
                for key, label in (("name", "name"), ("unit", "unit (what it's sold by)")):
                    if not v(key):
                        raise ValueError(f"A new product needs a {label}.")
            texts = {attr: v(key)[:160] for key, attr in (("name", "name"), ("genericName", "generic_name"), ("strength", "strength"), ("form", "form"), ("unit", "unit")) if mapped(key)}
            active = yes_no(v("isActive")) if mapped("isActive") else None
            prices = {key.removeprefix("price:"): money(v(key)) for key in body.mapping if key.startswith("price:") and mapped(key)}
            extras = {}
            for key in body.mapping:
                field = added.get(key.removeprefix("extra:")) if key.startswith("extra:") else None
                if field is None or not mapped(key):
                    continue
                raw = v(key)
                value = yes_no(raw) if field.type == "yes_no" else [x.strip() for x in raw.split(",") if x.strip()] if field.type == "multi_choice" else raw
                try:
                    extras[field.key] = _value(field, value)
                except ValueError as e:
                    raise ValueError(f"{field.label}: {e}") from None
        except ValueError as e:
            problems.append({"row": n, "message": str(e)})
            continue

        seen.add(code)
        if product is None:
            product = Product(code=code, name=texts["name"], unit=texts["unit"], is_active=True, extra={})
            db.add(product)
            existing[code] = product
            made += 1
        else:
            changed += 1
        for attr, value in texts.items():
            setattr(product, attr, value)
        if active is not None:
            product.is_active = active
        have = {pp.price_type_code: pp for pp in product.prices}
        for type_code, amount in prices.items():
            if type_code in have:
                have[type_code].amount_centavos = amount
            else:
                product.prices.append(ProductPrice(price_type_code=type_code, amount_centavos=amount))
        if extras:
            product.extra = {**(product.extra or {}), **extras}
    db.flush()
    if made or changed:
        audit(db, me, "products.imported", target=f"{made} added, {changed} updated", target_type="product")
    return made, changed, problems


def import_people(db: Session, me: User, body: ImportIn, get) -> tuple[int, int, list[dict]]:
    roles = {normal(r.name): r for r in db.scalars(select(Role))}
    teams = {normal(t.name): t for t in db.scalars(select(Team))}
    existing = {u.email.lower(): u for u in db.scalars(select(User))}
    seen: set[str] = set()
    made = changed = 0
    problems: list[dict] = []
    first_password = hash_password(body.password) if body.password else None
    for n, row in enumerate(body.rows, start=2):
        if not any(c.strip() for c in row):
            continue
        v = lambda key: get(row, key)  # noqa: E731
        try:
            email = v("email").lower()
            if not EMAIL.fullmatch(email):
                raise ValueError(f"{email or 'No email'}: not an email address.")
            if email in seen:
                raise ValueError(f"{email} is on another row of this file too.")
            role = roles.get(normal(v("role"))) if v("role") else None
            if v("role") and role is None:
                raise ValueError(f"There's no role called {v('role')}.")
            team_name = v("team")
            if team_name and normal(team_name) not in teams and not body.make_teams:
                raise ValueError(f"There's no team called {team_name}.")
            user = existing.get(email)
            if user is None:
                if not v("fullName"):
                    raise ValueError("A new person needs their full name.")
                if first_password is None:
                    raise ValueError("Set a first password for the people being added.")
        except ValueError as e:
            problems.append({"row": n, "message": str(e)})
            continue

        seen.add(email)
        team = None
        if team_name:
            team = teams.get(normal(team_name))
            if team is None:
                team = Team(name=team_name[:80])
                db.add(team)
                db.flush()
                teams[normal(team.name)] = team
        if user is None:
            role = role or roles.get(normal(SALESPERSON))
            user = User(email=email, full_name=v("fullName")[:120], password_hash=first_password, role_id=role.id, team_id=team.id if team else None)
            db.add(user)
            existing[email] = user
            made += 1
        else:
            if v("fullName"):
                user.full_name = v("fullName")[:120]
            if role:
                user.role_id = role.id
            if team:
                user.team_id = team.id
            changed += 1
    db.flush()
    keep_an_administrator(db)
    if made or changed:
        audit(db, me, "people.imported", target=f"{made} added, {changed} updated", target_type="user")
    return made, changed, problems


@router.post("/{kind}")
def run_import(access: CurrentAccess, me: CurrentUser, db: DB, kind: Kind, body: ImportIn) -> dict:
    allowed(access, kind)
    keys = {f["key"]: f for f in fields_of(db, kind)}
    missing = [f["label"] for f in keys.values() if f["required"] and body.mapping.get(f["key"]) is None]
    if kind == "products" and body.mapping.get("code") is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick the column that holds each product's code: it's how products are matched.")
    if kind == "people" and body.mapping.get("email") is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick the column that holds each person's email: it's how people are matched.")
    if kind == "people" and body.password and (why := check_password_rules(body.password)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"The first password: {why}")

    def get(row: list[str], key: str) -> str:
        i = body.mapping.get(key)
        return row[i].strip() if i is not None and 0 <= i < len(row) and row[i] is not None else ""

    made, changed, problems = (import_products if kind == "products" else import_people)(db, me, body, get)
    if body.dry_run:
        db.rollback()
    else:
        db.commit()
    return {
        "dryRun": body.dry_run,
        "added": made,
        "updated": changed,
        "problems": problems,
        # New products without some required column in the file still import when
        # every row that needs it has it; this names what wasn't picked at all.
        "unmapped": [m for m in missing if m not in ("Code", "Email")],
    }

