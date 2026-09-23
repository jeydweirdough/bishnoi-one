"""Set up the accounts database and starting data.

    uv run python -m app.seed                  migrate + divisions, teams, roles, permissions, pricing rules
    uv run python -m app.seed --demo           ...plus demo people, customers, products, promos and quotes
    uv run python -m app.seed --admin EMAIL --name "Full Name"
                                               ...plus an Admin (asks for a password)

Everything goes into the first company (Getmeds, app/tenancy.FIRST_ORG_ID),
which is created if it's missing.

Safe to run again: it only adds what's missing and never overwrites roles,
permissions or pricing rules an admin has edited.
"""

import argparse
import getpass
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import ensure_owner, members
from app.catalogue import seed_app_links
from app.config import API_DIR, Settings, get_settings
from app.db import make_engine, make_sessions
from app.fields import seed_fields
from app.models import (
    Assignment,
    Division,
    Headquarters,
    LocalCredential,
    Membership,
    Organization,
    PriceType,
    Product,
    ProductPrice,
    Profile,
    Promo,
    PromoDivision,
    PromoProduct,
    PromoTier,
    Role,
    RolePermission,
    Subdivision,
)
from app.modules import ALL_MODULES, DEFAULT_ROLES, MODULES
from app.platform import make_developer_admin
from app.order_settings import seed_order_settings
from app.price_book import load_issuers, load_price_types, load_products, load_promos, load_rules, seed_price_book
from app.pricing import PricedLine, PricedQuote, PricingError, price_quote
from app.quotes import QUOTE, quote_doc
from app.retention import seed_retention_rules
from app.schemas import QuoteIn
from app.scope import Scope, slugify
from app.security import hash_password
from app.store import build_records
from app.store.files import FileStore
from app.store.query import Cmp, Query
from app.store.records import Create, Records
from app.tenancy import FIRST_ORG_ID, all_companies, company_of, org_get, set_company

GENERAL = ("general", "General")
MD_TELESALES = ("md-telesales", "MD Telesales")

# Teams per division. MD Telesales sits under B&B, B2C, STC and URO. Divisions
# with no named team get "General", and so do the four with MD Telesales, for
# everyone outside it.
DEFAULT_TEAMS: dict[str, list[tuple[str, str]]] = {
    "b2c": [GENERAL, MD_TELESALES],
    "stc": [GENERAL, MD_TELESALES],
    "uro": [GENERAL, MD_TELESALES],
    "bnb": [GENERAL, MD_TELESALES],
    "b2b": [("nbd", "NBD"), ("crr", "CRR")],
    "hos": [("hospital", "Hospital"), ("telesales", "Telesales")],
    "bid": [("bidding", "Bidding")],
    "dispatch": [("pharmacy", "Pharmacy")],
}

# Headquarters from the old order app's lists. Which team each list belongs
# under is a best guess; admins move them in Settings -> Teams.
DEFAULT_HEADQUARTERS: dict[tuple[str, str], list[str]] = {
    ("bnb", "general"): ["CEBU", "DAVAO", "E. RODRIGUEZ", "EAST AVE", "NCL", "SOUTH LUZON", "TAFT"],
    ("hos", "hospital"): [
        "BAGUIO", "BICOL", "CABANATUAN", "CAMANAVA", "CAVITE", "CDO", "COMMONWEALTH", "DAVAO NORTH",
        "DAVAO SOUTH", "GENSAN", "ILOILO", "LAGUNA", "LAS PINAS", "MANILA VACANT", "MARIKINA", "NORTH CEBU",
        "PALAWAN", "PAMPANGA", "PARANAQUE", "PASAY", "QUEZON PROVINCE", "SOUTH CEBU", "TUGUEGARAO", "ZAMBOANGA",
    ],
    ("stc", "general"): ["CEBU", "COMMONWEALTH", "DAVAO", "KALAW", "NCL", "SOUTH LUZON", "TMC ORTIGAS"],
    ("uro", "general"): ["CEBU", "COMMONWEALTH", "DAVAO", "KALAW", "NCL", "SOUTH LUZON", "TMC ORTIGAS"],
}


def migrate() -> None:
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")


# The first company: Getmeds, whose data was there before there were companies.
FIRST_COMPANY = {
    "slug": "getmeds",
    "name": "Getmeds",
    "brand_name": "Getmeds",
    "template": "pharma_ph",
    "currency": "PHP",
    "minor_units": 2,
    "locale": "en-PH",
    "timezone": "Asia/Manila",
    "order_prefix": "GM",
}


def ensure_company(db: Session, org_id: str = FIRST_ORG_ID) -> Organization:
    """The company exists, and this session works in it from here on."""
    org = db.get(Organization, org_id)
    if org is None:
        if org_id != FIRST_ORG_ID:
            raise ValueError(f"no company {org_id}")
        org = Organization(id=org_id, **FIRST_COMPANY)
        db.add(org)
        db.commit()
    set_company(db, org_id)
    return org


def seed_reference(db: Session, org_id: str = FIRST_ORG_ID) -> None:
    ensure_company(db, org_id)
    divisions = [m for m in MODULES if m.is_division]
    for order, m in enumerate(divisions):
        division = org_get(db, Division, m.key)
        if division is None:
            db.add(Division(code=m.key, name=m.name, kind=m.kind.value, sort_order=order))
        else:
            # The name is the admins' to change (Settings -> Teams), so seeding
            # never writes over it. The built-in ones keep the module order, and
            # departments added since sort after them.
            division.kind, division.sort_order = m.kind.value, order
    db.flush()

    for m in divisions:
        for order, (code, name) in enumerate(DEFAULT_TEAMS.get(m.key, [GENERAL])):
            if org_get(db, Subdivision, m.key, code) is None:
                db.add(Subdivision(division_code=m.key, code=code, name=name, sort_order=order))
    db.flush()

    for (division, team), names in DEFAULT_HEADQUARTERS.items():
        for name in names:
            code = slugify(name)
            if org_get(db, Headquarters, division, team, code) is None:
                db.add(Headquarters(division_code=division, subdivision_code=team, code=code, name=name))

    if not db.scalar(select(func.count()).select_from(Role)):
        for order, (key, name, description, grants) in enumerate(DEFAULT_ROLES):
            db.add(Role(key=key, name=name, description=description, sort_order=order))
            db.flush()
            for module_key, actions in grants.items():
                for action in actions:
                    db.add(RolePermission(role_key=key, module_key=module_key, action=action))
    seed_app_links(db)
    seed_price_book(db)
    seed_retention_rules(db)
    seed_order_settings(db)
    seed_fields(db)
    db.commit()


def add_person(
    db: Session, email: str, name: str, password: str, grants: list[tuple[str, str, str | None, str | None]]
) -> Profile | None:
    """Adds the person to the session's company. None if they're in it already.

    Someone who already has an account (through another company) joins with
    the password they have; `password` is only for a new account."""
    person = db.scalar(select(Profile).where(Profile.email == email))
    if person is not None and db.scalar(select(Membership).where(Membership.user_id == person.id)):
        return None
    if person is None:
        person = Profile(email=email, full_name=name)
        db.add(person)
        db.flush()
        db.add(LocalCredential(user_id=person.id, password_hash=hash_password(password)))
    db.add(Membership(user_id=person.id))
    db.flush()
    for role, module, division, team in grants:
        db.add(Assignment(user_id=person.id, role_key=role, module_key=module, division_code=division, subdivision_code=team))
    db.flush()
    # The first person who can manage settings owns the company they set up.
    ensure_owner(db)
    db.commit()
    return person


DEMO_PASSWORD = "demo1234"

# email, name, [(role, module, division, team)]
DEMO_PEOPLE: list[tuple[str, str, list[tuple[str, str, str | None, str | None]]]] = [
    ("carmen@pharmacrm.test", "Carmen Villanueva", [("admin", ALL_MODULES, None, None)]),
    ("ramon@pharmacrm.test", "Ramon Santos", [("executive", ALL_MODULES, None, None)]),
    ("lorna@pharmacrm.test", "Lorna Bautista", [("division_head", "bnb", "bnb", None)]),
    ("paolo@pharmacrm.test", "Paolo Mendoza", [("team_lead", "bnb", "bnb", "md-telesales")]),
    # Two teams in two divisions. She must see B&B/MD Telesales and B2C/General,
    # and not B2C/MD Telesales or B&B/General.
    ("ana@pharmacrm.test", "Ana Reyes", [("rep", "bnb", "bnb", "md-telesales"), ("rep", "b2c", "b2c", "general")]),
    ("ben@pharmacrm.test", "Ben Cruz", [("rep", "b2c", "b2c", "md-telesales")]),
    # A team lead in a division that quotes from a price list, so the team
    # prices screen has something to show. B&B's leads can't: it quotes with
    # notes only, by its own pricing rules.
    ("tess@pharmacrm.test", "Tess Aquino", [("team_lead", "b2c", "b2c", "general")]),
    ("grace@pharmacrm.test", "Grace Lim", [("rep", "hos", "hos", "hospital")]),
    ("joy@pharmacrm.test", "Joy Navarro", [("department_staff", "finance", None, None)]),
    ("iris@pharmacrm.test", "Iris Dela Cruz", [("department_staff", "inventory", None, None)]),

    # One person per remaining division and team, so every sales perspective can
    # be signed into and looked at.
    ("nena@pharmacrm.test", "Nena Gutierrez", [("rep", "stc", "stc", "md-telesales")]),
    ("rico@pharmacrm.test", "Rico Padilla", [("rep", "uro", "uro", "md-telesales")]),
    ("marlon@pharmacrm.test", "Marlon Yap", [("rep", "b2b", "b2b", "nbd")]),
    ("dina@pharmacrm.test", "Dina Salazar", [("rep", "b2b", "b2b", "crr")]),
    ("elmer@pharmacrm.test", "Elmer Tan", [("rep", "hos", "hos", "telesales")]),
    # BID bids rather than quoting from a price list, so its quotes carry notes.
    ("rosa@pharmacrm.test", "Rosa Ferrer", [("rep", "bid", "bid", "bidding")]),
    # A lead and a division head outside B&B, so those views can be compared.
    ("vicky@pharmacrm.test", "Vicky Ong", [("team_lead", "hos", "hos", "hospital")]),
    ("noel@pharmacrm.test", "Noel Ramos", [("division_head", "b2b", "b2b", None)]),

    # The roles that work across the company rather than in one team. Assigned to
    # every module: a role only grants what it says, so this hands each of them
    # their own desk and nothing else.
    ("mila@pharmacrm.test", "Mila Aguilar", [("management", ALL_MODULES, None, None)]),
    ("fely@pharmacrm.test", "Fely Domingo", [("finance_staff", ALL_MODULES, None, None)]),
    ("bong@pharmacrm.test", "Bong Rivera", [("dispatch_staff", ALL_MODULES, None, None)]),

    # One per department that has no screens yet, so what they see today -- and
    # what they will see when their screens are built -- can be checked.
    ("teresa@pharmacrm.test", "Teresa Abad", [("department_staff", "hr", None, None)]),
    ("alex@pharmacrm.test", "Alex Soriano", [("department_staff", "regulatory", None, None)]),
    ("karla@pharmacrm.test", "Karla Ilagan", [("department_staff", "inlicensing", None, None)]),
    ("ruth@pharmacrm.test", "Ruth Sarmiento", [("department_staff", "pharmacy", None, None)]),
    ("deo@pharmacrm.test", "Deo Castillo", [("department_staff", "exec", None, None)]),

]

# Jun is the Developer Admin, and he is not in the list above for two reasons:
# the tier is not a role, and he is not a member of any company. He belongs to
# the platform, above all of them (app/platform.py), which is what lets him
# reach every one -- and why he appears in nobody's People screen.
DEMO_DEVELOPER_ADMINS = [("jun@pharmacrm.test", "Jun Espino")]

# scope, headquarters, name, kind, specialty, phone, city, status, owner (first name)
DEMO_CUSTOMERS = [
    ("bnb/md-telesales", None, "Dr. Alma Dizon", "doctor", "Pediatrics", "0917 555 0101", "Quezon City", "active", "ana"),
    ("bnb/md-telesales", None, "Dr. Victor Salcedo", "doctor", "Internal Medicine", "0917 555 0102", "Makati", "lead", "ana"),
    ("bnb/md-telesales", None, "Dr. Irene Galang", "doctor", "OB-GYN", "0917 555 0103", "Pasig", "active", "paolo"),
    ("bnb/md-telesales", None, "Sta. Lucia Drugstore", "pharmacy", None, "0917 555 0104", "Cainta", "active", "paolo"),
    ("bnb/general", "cebu", "Mercado Family Clinic", "clinic", None, "0917 555 0111", "Cebu City", "active", "lorna"),
    ("bnb/general", "taft", "Dr. Noel Tan", "doctor", "Cardiology", "0917 555 0112", "Manila", "lead", "lorna"),
    ("b2c/general", None, "Maria Lopez", "patient", None, "0917 555 0121", "Parañaque", "active", "ana"),
    ("b2c/general", None, "Jose Ramos", "patient", None, "0917 555 0122", "Las Piñas", "lead", "ana"),
    ("b2c/md-telesales", None, "Dr. Cora Aquino", "doctor", "Dermatology", "0917 555 0131", "Taguig", "active", "ben"),
    ("b2c/md-telesales", None, "Dr. Felix Uy", "doctor", "Family Medicine", "0917 555 0132", "Mandaluyong", "lead", "ben"),
    ("stc/md-telesales", None, "Dr. Hilda Ong", "doctor", "Endocrinology", "0917 555 0141", "San Juan", "active", None),
    ("uro/general", "kalaw", "Dr. Marco Villareal", "doctor", "Urology", "0917 555 0151", "Manila", "active", None),
    ("b2b/nbd", None, "Northpoint Distributors", "distributor", None, "0917 555 0161", "Valenzuela", "lead", None),
    ("b2b/crr", None, "Healthway Pharmacy Chain", "company", None, "0917 555 0162", "Pasig", "active", None),
    ("hos/hospital", "iloilo", "St. Anne General Hospital", "hospital", None, "0917 555 0171", "Iloilo City", "active", "grace"),
    ("hos/hospital", "north-cebu", "Riverside Medical Center", "hospital", None, "0917 555 0172", "Danao", "lead", "grace"),
]

# customer, days ago, kind, outcome, summary, by
DEMO_ACTIVITIES = [
    ("Dr. Alma Dizon", 2, "call", "reached", "Talked about the new pediatric syrup. Wants samples and the price list.", "ana"),
    ("Dr. Victor Salcedo", 1, "call", "no_answer", "No answer on the clinic line.", "ana"),
    ("Dr. Irene Galang", 5, "visit", "reached", "Clinic visit. Interested in the prenatal vitamins line.", "paolo"),
    ("Sta. Lucia Drugstore", 3, "message", None, "Sent the updated product list by SMS.", "paolo"),
    ("Mercado Family Clinic", 6, "note", None, "Clinic is moving to a bigger space next month.", "lorna"),
    ("Maria Lopez", 0, "call", "reached", "Refill reminder. Will reorder next week.", "ana"),
    ("Dr. Cora Aquino", 1, "call", "call_back", "Asked to be called back on Friday afternoon.", "ben"),
    ("St. Anne General Hospital", 4, "visit", "reached", "Met the pharmacy head about the Q4 formulary review.", "grace"),
]

# customer, due in days, title, assignee, done
DEMO_FOLLOW_UPS = [
    ("Dr. Alma Dizon", 0, "Send samples and the price list", "ana", False),
    ("Dr. Victor Salcedo", -1, "Call back after 3pm", "ana", False),
    ("Dr. Irene Galang", 3, "Bring prenatal vitamins brochure", "paolo", False),
    ("Sta. Lucia Drugstore", -3, "Confirm they got the product list", "paolo", True),
    ("Maria Lopez", 5, "Check if the reorder went through", "ana", False),
    ("Jose Ramos", 1, "First call: introduce the maintenance program", "ana", False),
    ("Dr. Cora Aquino", 0, "Call back (Friday afternoon)", "ben", False),
    ("St. Anne General Hospital", -2, "Send formulary submission documents", "grace", False),
]


def add_developer_admin(db: Session, email: str, name: str, password: str) -> Profile | None:
    """An account that belongs to the platform rather than to a company.

    Deliberately no Membership: a Developer Admin does not work in any company,
    which is why they turn up in nobody's People screen and why their reach
    comes from `platform_admins` instead of from a role. None if already there."""
    with all_companies(db):
        person = db.scalar(select(Profile).where(Profile.email == email))
        if person is not None:
            make_developer_admin(db, email)
            return None
        person = Profile(email=email, full_name=name)
        db.add(person)
        db.flush()
        db.add(LocalCredential(user_id=person.id, password_hash=hash_password(password)))
        db.commit()
    make_developer_admin(db, email)
    return person


def seed_demo_people(db: Session) -> None:
    for email, name, grants in DEMO_PEOPLE:
        add_person(db, email, name, DEMO_PASSWORD, grants)
    for email, name in DEMO_DEVELOPER_ADMINS:
        add_developer_admin(db, email, name, DEMO_PASSWORD)


def seed_demo_records(records: Records, db: Session, settings: Settings) -> bool:
    records = records.for_org(company_of(db))
    every_scope = frozenset(
        Scope(d, s) for d, s in db.execute(select(Subdivision.division_code, Subdivision.code))
    )
    if records.count(Query("customer", every_scope)):
        return False

    people = {p.email.split("@")[0]: p for p in members(db, active_only=False)}
    now = datetime.now(UTC)
    day = datetime.now(ZoneInfo(settings.timezone)).date()

    def iso(moment: datetime) -> str:
        return moment.isoformat(timespec="seconds").replace("+00:00", "Z")

    customers: dict[str, dict] = {}
    mutations = []
    for key, hq, name, kind, specialty, phone, city, status, owner in DEMO_CUSTOMERS:
        scope = Scope.from_key(key)
        person = people.get(owner) if owner else None
        doc = {
            "_id": str(uuid.uuid4()),
            "_type": "customer",
            **scope.stamp(),
            "headquarters": hq,
            "name": name,
            "sortName": name.casefold(),
            "kind": kind,
            "specialty": specialty,
            "phone": phone,
            "phoneDigits": "".join(ch for ch in phone if ch.isdigit()),
            "city": city,
            "status": status,
            "ownerId": person.id if person else None,
            "ownerName": person.full_name if person else None,
            "createdAt": iso(now - timedelta(days=30)),
            "updatedAt": iso(now - timedelta(days=30)),
        }
        doc = {k: v for k, v in doc.items() if v is not None}
        customers[name] = doc

    for name, days_ago, kind, outcome, summary, by in DEMO_ACTIVITIES:
        customer, person = customers[name], people[by]
        occurred = iso(now - timedelta(days=days_ago, hours=2))
        activity = {
            "_id": str(uuid.uuid4()),
            "_type": "activity",
            **Scope.of(customer).stamp(),
            "customerId": customer["_id"],
            "kind": kind,
            "summary": summary,
            "occurredAt": occurred,
            "byId": person.id,
            "byName": person.full_name,
            "createdAt": occurred,
        }
        if outcome:
            activity["outcome"] = outcome
        customer["lastContactAt"] = max(customer.get("lastContactAt", ""), occurred)
        mutations.append(Create(activity))

    for name, due_in, title, assignee, done in DEMO_FOLLOW_UPS:
        customer, person = customers[name], people[assignee]
        follow_up = {
            "_id": str(uuid.uuid4()),
            "_type": "followUp",
            **Scope.of(customer).stamp(),
            "customerId": customer["_id"],
            "title": title,
            "dueOn": (day + timedelta(days=due_in)).isoformat(),
            "status": "done" if done else "open",
            "assigneeId": person.id,
            "assigneeName": person.full_name,
            "createdAt": iso(now - timedelta(days=7)),
            "createdById": person.id,
        }
        if done:
            follow_up |= {"doneAt": iso(now - timedelta(days=2)), "doneById": person.id, "doneByName": person.full_name}
        mutations.append(Create(follow_up))

    records.commit([Create(c) for c in customers.values()] + mutations)
    return True


# code, name, generic name, strength, form, unit, prices in pesos by price type
DEMO_PRODUCTS: list[tuple[str, str, str, str | None, str, str, dict[str, int]]] = [
    ("AMOX-500", "Amoxicillin 500 mg", "Amoxicillin", "500 mg", "Capsule", "Box of 100",
     {"srp": 1450, "patient": 1350, "doctor": 1200, "drugstore-hospital": 1100, "distributor": 980, "government": 950}),
    ("PARA-SYR", "Paracetamol Syrup", "Paracetamol", "250 mg/5 mL", "Syrup", "Bottle, 60 mL",
     {"srp": 95, "patient": 89, "doctor": 80, "drugstore-hospital": 72, "distributor": 65, "government": 60}),
    ("ASC-500", "Ascorbic Acid 500 mg", "Ascorbic Acid", "500 mg", "Tablet", "Box of 100",
     {"srp": 520, "patient": 480, "doctor": 430, "drugstore-hospital": 400, "distributor": 360, "government": 340}),
    ("MET-500", "Metformin 500 mg", "Metformin", "500 mg", "Tablet", "Box of 100",
     {"srp": 780, "patient": 720, "doctor": 650, "drugstore-hospital": 600, "distributor": 540, "government": 500}),
    # No Government Price yet, so Inventory's "missing prices" count has something to show.
    ("PNV-30", "Prenatal Multivitamins", "Multivitamins + Folic Acid", None, "Capsule", "Box of 30",
     {"srp": 890, "patient": 840, "doctor": 760, "drugstore-hospital": 700, "distributor": 630}),
]

# name, kind, values, product codes (None: every product), divisions, starts and ends (days from today)
DEMO_PROMOS: list[tuple[str, str, dict, list[str] | None, list[str], int, int | None]] = [
    ("Vitamin C 10% off", "percent", {"percent_bp": 1000}, ["ASC-500"], ["b2c", "stc", "hos"], -7, 60),
    ("₱10 off Paracetamol Syrup", "amount", {"amount_centavos": 1000}, ["PARA-SYR"], ["b2c"], -7, 30),
    ("Buy 10, get 1 Amoxicillin", "free_goods", {"buy_qty": 10, "free_qty": 1}, ["AMOX-500"], ["hos", "b2b"], -14, 45),
    ("Volume discount", "tiered", {"tiers": [(20, 500), (50, 800)]}, None, ["hos", "b2b"], -30, None),
]


def seed_demo_catalog(db: Session, settings: Settings) -> bool:
    if db.scalar(select(func.count()).select_from(Product)):
        return False
    day = datetime.now(ZoneInfo(settings.timezone)).date()
    known = set(db.scalars(select(PriceType.code)))
    products: dict[str, Product] = {}
    for code, name, generic, strength, form, unit, prices in DEMO_PRODUCTS:
        products[code] = Product(
            code=code,
            name=name,
            # Generic name, Strength and Form are pharma's own product fields
            # now; the columns are kept in step behind them while the web app
            # still reads them by name (see routers/inventory.py).
            details={k: v for k, v in (("generic_name", generic), ("strength", strength), ("form", form)) if v},
            generic_name=generic,
            strength=strength,
            form=form,
            unit=unit,
            prices=[ProductPrice(price_type_code=t, amount_centavos=pesos * 100) for t, pesos in prices.items() if t in known],
        )
        db.add(products[code])
    db.flush()
    for name, kind, values, codes, divisions, starts, ends in DEMO_PROMOS:
        db.add(
            Promo(
                name=name,
                kind=kind,
                percent_bp=values.get("percent_bp"),
                amount_centavos=values.get("amount_centavos"),
                buy_qty=values.get("buy_qty"),
                free_qty=values.get("free_qty"),
                starts_on=day + timedelta(days=starts),
                ends_on=day + timedelta(days=ends) if ends is not None else None,
                all_products=codes is None,
                tiers=[PromoTier(min_qty=q, percent_bp=bp) for q, bp in values.get("tiers", [])],
                products=[PromoProduct(product_id=products[c].id) for c in codes or []],
                divisions=[PromoDivision(division_code=d) for d in divisions],
            )
        )
    db.commit()
    return True


# A one-page PDF standing in for a scanned guarantee letter.
DEMO_LETTER_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 420 160]/Contents 4 0 R"
    b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 51>>stream\nBT /F1 16 Tf 24 90 Td (Demo guarantee letter) Tj ET\nendstream\nendobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)

# customer, made by, the quote with product codes and promo names
DEMO_QUOTES: list[tuple[str, str, dict]] = [
    # Waits for Finance to check the DSWD letter.
    ("Maria Lopez", "ana", {
        "priceType": "patient", "payer": "dswd",
        "notes": "Medicines for her son. DSWD assistance approved at the NCR field office.",
        "lines": [
            {"product": "ASC-500", "quantity": 2, "promo": "Vitamin C 10% off"},
            {"product": "PARA-SYR", "quantity": 3, "promo": "₱10 off Paracetamol Syrup"},
        ],
        "letter": {"number": "DSWD-NCR-2026-01482", "daysAgo": 3, "pesos": 1101},
    }),
    # A 15% manual discount on top of the volume tier: over HOS's 10% limit, so Finance approves.
    ("St. Anne General Hospital", "grace", {
        "priceType": "drugstore-hospital",
        "notes": "Q4 formulary stock-up. Asked for an extra discount to match a competitor's offer.",
        "lines": [
            {"product": "AMOX-500", "quantity": 30, "promo": "Volume discount", "discount": {"kind": "percent", "value": 1500}},
        ],
    }),
    # B2C with an Rx: Doctor's Price. Nothing for Finance.
    ("Dr. Cora Aquino", "ben", {"priceType": "doctor", "rx": True, "lines": [{"product": "MET-500", "quantity": 5}]}),
]


def seed_demo_quotes(records: Records, db: Session, settings: Settings, files: FileStore) -> bool:
    records, files = records.for_org(company_of(db)), files.for_org(company_of(db))
    every_scope = frozenset(
        Scope(d, s) for d, s in db.execute(select(Subdivision.division_code, Subdivision.code))
    )
    if records.count(Query(QUOTE, every_scope)):
        return False
    customers = {c["name"]: c for c in records.find(Query("customer", every_scope, limit=5000))}
    people = {p.email.split("@")[0]: p for p in members(db, active_only=False)}
    products = {p.code: p for p in db.scalars(select(Product))}
    day: date = datetime.now(ZoneInfo(settings.timezone)).date()
    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    mutations = []
    for name, by, spec in DEMO_QUOTES:
        customer, person = customers.get(name), people.get(by)
        if customer is None or person is None or any(line["product"] not in products for line in spec["lines"]):
            continue
        scope = Scope.of(customer)
        promos = load_promos(db, scope.division, day)
        promo_ids = {p.name: p.id for p in promos.values()}
        letter = spec.get("letter")
        body = QuoteIn.model_validate(
            {
                "priceType": spec["priceType"],
                "rx": spec.get("rx", False),
                "payer": spec.get("payer", "self"),
                "notes": spec.get("notes"),
                "lines": [
                    {
                        "productId": products[line["product"]].id,
                        "quantity": line["quantity"],
                        "promoId": promo_ids.get(line.get("promo", "")),
                        "discount": line.get("discount"),
                    }
                    for line in spec["lines"]
                ],
                "letter": (
                    {
                        "number": letter["number"],
                        "issuedOn": (day - timedelta(days=letter["daysAgo"])).isoformat(),
                        "amountCentavos": letter["pesos"] * 100,
                    }
                    if letter
                    else None
                ),
            }
        )
        issuers = load_issuers(db)
        try:
            priced = price_quote(
                body,
                load_rules(db, scope.division),
                load_price_types(db),
                load_products(db, {line.product_id for line in body.lines}),
                promos,
                issuers,
            )
        except PricingError:  # an admin changed the rules this demo relies on; skip it
            continue
        letter_file = None
        if letter:
            letter_file = {
                "ref": files.put(DEMO_LETTER_PDF),
                "name": f"{letter['number']}.pdf",
                "contentType": "application/pdf",
                "ext": "pdf",
                "size": len(DEMO_LETTER_PDF),
            }
        mutations.append(
            Create(
                quote_doc(
                    quote_id=str(uuid.uuid4()),
                    scope=scope,
                    customer=customer,
                    quote=body,
                    priced=priced,
                    payer_name=issuers.get(body.payer),
                    letter_file=letter_file,
                    user=person,
                    now=now,
                )
            )
        )
    records.commit(mutations)
    return bool(mutations)


# customer -> how many days ago they got a quote: a year of history so the
# retention figures have something to show (kept, at risk, lost and new).
DEMO_HISTORY: dict[str, tuple[int, ...]] = {
    "Maria Lopez": (200, 150, 110, 60),  # kept, now at risk
    "Jose Ramos": (300, 250),  # lost long ago
    "Dr. Alma Dizon": (170, 120, 75, 20),  # kept
    "Dr. Victor Salcedo": (160, 100),  # lost lately
    "Dr. Irene Galang": (140, 95, 50),  # kept, at risk
    "Sta. Lucia Drugstore": (130, 70, 25),  # kept
    "Mercado Family Clinic": (190, 120, 88),  # kept, close to lost
    "Dr. Noel Tan": (35,),  # new
    "Dr. Cora Aquino": (150, 100),
    "Dr. Felix Uy": (110,),  # lost lately
    "Dr. Hilda Ong": (180, 120, 60, 10),
    "Dr. Marco Villareal": (220, 140, 80),
    "Northpoint Distributors": (100, 40),
    "Healthway Pharmacy Chain": (170, 115, 55, 12),
    "St. Anne General Hospital": (160, 125, 95, 64),
    "Riverside Medical Center": (150, 105),
}


def seed_demo_history(records: Records, db: Session, settings: Settings) -> bool:
    """Back-dated SRP quotes for the demo customers. Added once: skipped when any quote is over 30 days old."""
    records = records.for_org(company_of(db))
    every_scope = frozenset(Scope(d, s) for d, s in db.execute(select(Subdivision.division_code, Subdivision.code)))
    month_ago = (datetime.now(UTC) - timedelta(days=30)).isoformat(timespec="seconds").replace("+00:00", "Z")
    if records.count(Query(QUOTE, every_scope, (Cmp("createdAt", "<", month_ago),))):
        return False
    srp = load_price_types(db).get("srp")
    products = [p for p in load_products(db).values() if srp and srp.code in p.prices]
    if srp is None or not products:
        return False
    customers = {c["name"]: c for c in records.find(Query("customer", every_scope, limit=5000))}
    people = {p.id: p for p in members(db, active_only=False)}
    fallback = next((p for p in people.values() if p.email == "ramon@pharmacrm.test"), None)

    mutations = []
    for n, (name, days) in enumerate(DEMO_HISTORY.items()):
        customer = customers.get(name)
        person = people.get(customer.get("ownerId")) if customer else None
        if customer is None or (person or fallback) is None:
            continue
        for i, days_ago in enumerate(days):
            product = products[(n + i) % len(products)]
            quantity = 5 + (n * 3 + i * 7) % 16
            unit = product.prices[srp.code]
            line = PricedLine(product.id, product.code, product.name, product.unit, quantity, 0, unit, unit * quantity,
                              None, None, 0, None, None, 0, unit * quantity)
            priced = PricedQuote(srp, (line,), line.gross, 0, 0, line.total, ())
            body = QuoteIn.model_validate({"priceType": srp.code, "lines": [{"productId": product.id, "quantity": quantity}]})
            at = datetime.now(UTC) - timedelta(days=days_ago, hours=3)
            mutations.append(
                Create(
                    quote_doc(
                        quote_id=str(uuid.uuid4()),
                        scope=Scope.of(customer),
                        customer=customer,
                        quote=body,
                        priced=priced,
                        payer_name=None,
                        letter_file=None,
                        user=person or fallback,
                        now=at.isoformat(timespec="seconds").replace("+00:00", "Z"),
                    )
                )
            )
    records.commit(mutations)
    return bool(mutations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed", description=__doc__.split("\n")[0])
    parser.add_argument("--demo", action="store_true", help="add demo people and demo customers")
    parser.add_argument("--admin", metavar="EMAIL", help="create an Admin with this email")
    parser.add_argument("--name", help="the admin's full name (with --admin)")
    args = parser.parse_args(argv)
    if args.admin and not args.name:
        parser.error("--admin needs --name")

    settings = get_settings()
    migrate()
    sessions = make_sessions(make_engine(settings.database_url))
    with sessions() as db:
        seed_reference(db)
        print("Divisions, teams, headquarters, roles, permissions and pricing rules are in place.")

        if args.admin:
            password = getpass.getpass(f"Password for {args.admin} (8+ characters): ")
            if len(password) < 8:
                print("Password too short; nothing created.", file=sys.stderr)
                return 1
            created = add_person(db, args.admin.lower(), args.name, password, [("admin", ALL_MODULES, None, None)])
            print(f"Admin {args.admin} created." if created else f"{args.admin} already exists; left as is.")

        if args.demo:
            seed_demo_people(db)
            print(f"Demo people ready (password: {DEMO_PASSWORD}).")
            records = build_records(settings)
            if seed_demo_records(records, db, settings):
                print(f"Demo customers added to the {records.kind} store.")
            else:
                print("Customers already exist; demo customers skipped.")
            if seed_demo_catalog(db, settings):
                print("Demo products, prices and promos added.")
            else:
                print("Products already exist; demo products skipped.")
            if seed_demo_quotes(records, db, settings, FileStore(settings.files_path)):
                print("Demo quotes added.")
            else:
                print("Quotes already exist; demo quotes skipped.")
            if seed_demo_history(records, db, settings):
                print("A year of demo quote history added, for the retention figures.")
            else:
                print("Quote history already there; skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
