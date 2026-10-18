"""The Rx team's customer form (STC, URO and B&B): its own fields and its own
customer types, set up once; safe to run again (nothing is made twice, and
what an administrator changed since is left alone where it can be).

    uv run python -m app.tools.rx_form

What it does, for the Rx teams only:
- adds: category, business potential, landline and
  region for every Rx customer; department, qualification or title, hospital
  name and a Personal section (gender, marital status, birthday, anniversary,
  interests) for people; and a Professional profiling section for doctors,
  fellows and residents (patients a day, products of interest, top 3
  molecules with patients a week);
- keeps Industry, Lead source, Website and Country off their form;
- offers them their own customer types (Doctor, Fellow, Resident...), and not
  the general ones (Prospect, Customer, Partner, Inactive);
- and, for everyone, calls the owner "Assigned to".
The B2C team gets the Patient type.
"""

import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import make_engine, make_sessions
from app.tenants import for_tool
from app.migrate import upgrade
from app.models import Company, CustomerType, FormField, FormSection, Team
from app.pricing import sales_settings
from app.terms import PHARMA

TOOL = "rx form tool"
RX_TEAMS = ("STC", "URO", "B&B")

DEPARTMENTS = {
    "MED ONCO": "Medical oncology",
    "HEMA": "Hematology",
    "URO": "Urology",
    "GYN ONCO": "Gynecologic oncology",
    "NEPHRO": "Nephrology",
    "SURG ONCO": "Surgical oncology",
    "URO ONCO": "Uro-oncology",
    "PEDIA ONCO": "Pediatric oncology",
    "PEDIA HEMA": "Pediatric hematology",
}

REGIONS = {
    "NCR": "National Capital Region",
    "CAR": "Cordillera Administrative Region",
    "Region I": "Ilocos Region",
    "Region II": "Cagayan Valley",
    "Region III": "Central Luzon",
    "Region IV-A": "CALABARZON",
    "MIMAROPA": "Southwestern Tagalog Region",
    "Region V": "Bicol Region",
    "Region VI": "Western Visayas",
    "NIR": "Negros Island Region",
    "Region VII": "Central Visayas",
    "Region VIII": "Eastern Visayas",
    "Region IX": "Zamboanga Peninsula",
    "Region X": "Northern Mindanao",
    "Region XI": "Davao Region",
    "Region XII": "SOCCSKSARGEN",
    "Region XIII": "Caraga",
    "BARMM": "Bangsamoro",
}

CATEGORIES = {"A": "A: top priority", "B": "B: regular", "C": "C: occasional"}

# Who each field is asked of, by customer type. People are profiled; a
# hospital or distributor is asked only what fits an organisation.
DOCTORS = ["doctor", "fellow", "resident"]
PEOPLE = [*DOCTORS, "or_nurse", "pharmacist", "purchase_head", "other_kbl"]

# (section title, key, label, type, extra settings), in the order they appear.
# "types": the customer types it's asked of (none: every type).
FIELDS = [
    ("The customer", "x_department", "Department", "choice", {"options": DEPARTMENTS, "types": PEOPLE}),
    ("The customer", "x_qualification", "Qualification / title", "text", {"placeholder": "e.g. MD, FPCP, Dr.", "types": PEOPLE}),
    ("The customer", "x_hospital", "Hospital name", "text", {"types": PEOPLE}),
    ("The customer", "x_category", "Category", "choice", {"options": CATEGORIES}),
    ("The customer", "x_potential", "Approximate business potential", "money", {"help_text": "Roughly how much business they could bring, in pesos a month."}),
    ("How to reach them", "x_landline", "Landline", "phone", {}),
    ("How to reach them", "x_region", "Region", "choice", {"options": REGIONS}),
    ("Personal", "x_gender", "Gender", "choice", {"options": {"Male": "", "Female": ""}, "types": PEOPLE}),
    ("Personal", "x_marital_status", "Marital status", "choice", {"options": {"Single": "", "Married": "", "Widowed": "", "Separated": ""}, "types": PEOPLE}),
    ("Personal", "x_birth_date", "Date of birth", "date", {"types": PEOPLE}),
    ("Personal", "x_anniversary", "Marriage anniversary", "date", {"types": PEOPLE}),
    ("Personal", "x_interests", "Interests and hobbies", "long_text", {"types": PEOPLE, "help_text": "Their life outside work: family, sports, what they enjoy."}),
    ("Professional profiling", "x_patients_per_day", "Patients per day", "number", {"types": DOCTORS, "help_text": "About how many patients they see a day."}),
    ("Professional profiling", "x_product_interest", "Products of interest", "products", {"types": DOCTORS, "help_text": "Which of our products they're interested in."}),
    ("Professional profiling", "x_molecule_1", "Top molecule 1", "molecule", {"types": DOCTORS}),
    ("Professional profiling", "x_molecule_1_patients", "Patients per week (molecule 1)", "number", {"types": DOCTORS}),
    ("Professional profiling", "x_molecule_2", "Top molecule 2", "molecule", {"types": DOCTORS}),
    ("Professional profiling", "x_molecule_2_patients", "Patients per week (molecule 2)", "number", {"types": DOCTORS}),
    ("Professional profiling", "x_molecule_3", "Top molecule 3", "molecule", {"types": DOCTORS}),
    ("Professional profiling", "x_molecule_3_patients", "Patients per week (molecule 3)", "number", {"types": DOCTORS}),
]

# Built-in fields the Rx form goes without.
NOT_FOR_RX = ("industry", "leadSource", "website", "country")

RX_TYPES = [
    ("doctor", "Doctor"),
    ("fellow", "Fellow"),
    ("resident", "Resident"),
    ("or_nurse", "OR nurse"),
    ("pharmacist", "Pharmacist"),
    ("purchase_head", "Purchase head"),
    ("other_kbl", "Other KBL"),
    ("distributor", "Distributor"),
    ("hospital", "Hospital"),
    ("dialysis_center", "Dialysis center"),
    ("drugstore", "Drugstore (TGP, Mercury)"),
]
GENERAL_TYPES = ("prospect", "customer", "partner", "inactive")


def add_to(items: list | None, more: list[str]) -> list[str]:
    return list(dict.fromkeys([*(items or []), *more]))


def set_up(db: Session) -> list[str]:
    """Sets the Rx form up; returns what it did, in words."""
    teams = {t.name.upper(): t for t in db.scalars(select(Team))}
    rx = [teams[n.upper()].id for n in RX_TEAMS if n.upper() in teams]
    if not rx:
        raise SystemExit(f"None of the Rx teams ({', '.join(RX_TEAMS)}) are here yet. Add them in People and access > Teams first.")
    done: list[str] = []
    sections = {s.title: s for s in db.scalars(select(FormSection).where(FormSection.entity == "company"))}
    fields = {f.key: f for f in db.scalars(select(FormField).where(FormField.entity == "company"))}

    for title in ("Professional profiling", "Personal"):
        if title not in sections:
            last = max((s.sort_order for s in sections.values()), default=0)
            sections[title] = FormSection(entity="company", title=title, columns=2, sort_order=last + 1)
            db.add(sections[title])
            db.flush()
            done.append(f"Added the {title} section")

    for title, key, label, kind, more in FIELDS:
        section = sections[title]
        field = fields.get(key)
        if field is None:
            here = [f.sort_order for f in fields.values() if f.section_id == section.id]
            options = more.get("options", {})
            field = FormField(
                entity="company",
                key=key,
                label=label,
                type=kind,
                standard=False,
                locked=False,
                options=list(options),
                option_names={o: n for o, n in options.items() if n},
                unique=more.get("unique", False),
                help_text=more.get("help_text"),
                placeholder=more.get("placeholder"),
                section_id=section.id,
                sort_order=max(here, default=0) + 1,
            )
            db.add(field)
            fields[key] = field
            done.append(f"Added {label}")
        field.only_teams = add_to(field.only_teams, rx)
        # Which customers it's asked of, unless an administrator already chose.
        if more.get("types") and not field.only_types and not field.except_types:
            field.only_types = list(more["types"])

    # The customer code is the system's now (CRM-000001, app/models.py): the
    # field once typed in goes, or is hidden if anything was typed in it.
    typed = fields.get("x_customer_code")
    if typed is not None:
        used = any((extra or {}).get("x_customer_code") for (extra,) in db.execute(select(Company.extra)))
        if used:
            typed.hidden = True
        else:
            db.delete(typed)
        done.append("Took the typed customer code off the form: the system gives each customer its code")

    for key in NOT_FOR_RX:
        if key in fields:
            fields[key].except_teams = add_to(fields[key].except_teams, rx)
    done.append("Kept Industry, Lead source, Website and Country off the Rx form")

    owner = fields.get("ownerId")
    if owner is not None and owner.label == "Owner":
        owner.label = "Assigned to"
        done.append('Owner is now called "Assigned to"')
    if owner is not None and owner.section_id:
        section = db.get(FormSection, owner.section_id)
        if section is not None and section.title == "Who looks after it":
            section.title = "Assignment"

    # A pharmaceutical company's words (Settings → Terms), unless it has chosen its own.
    settings_row = sales_settings(db)
    if not settings_row.terms:
        settings_row.terms = dict(PHARMA)
        done.append("Terms: doctors, clinic, detailing, molecule (Settings → Terms)")

    types = {t.code: t for t in db.scalars(select(CustomerType))}
    order = max((t.sort_order for t in types.values()), default=0)
    for code, name in RX_TYPES:
        kind = types.get(code)
        if kind is None:
            if db.scalar(select(CustomerType.code).where(func.lower(CustomerType.name) == name.lower())):
                continue  # one of that name already, under another code
            order += 1
            kind = CustomerType(code=code, name=name, color="blue", sort_order=order, is_active=True, only_teams=[], except_teams=[])
            db.add(kind)
            types[code] = kind
            done.append(f"Added the {name} type")
        if not kind.is_active:
            kind.is_active = True
            done.append(f"Switched the {kind.name} type on")
        # Doctor is everyone's (field agents visit doctors); the rest are Rx's.
        if code != "doctor":
            kind.only_teams = add_to(kind.only_teams, rx)
    for code in GENERAL_TYPES:
        if code in types:
            types[code].except_teams = add_to(types[code].except_teams, rx)
    done.append("Kept Prospect, Customer, Partner and Inactive off the Rx type list")

    b2c = teams.get("B2C")
    if b2c is not None and "patient" not in types:
        order += 1
        db.add(CustomerType(code="patient", name="Patient", color="purple", sort_order=order, is_active=True, only_teams=[b2c.id], except_teams=[]))
        done.append("Added the Patient type, for B2C")

    audit(db, TOOL, "form.updated", target="company form (Rx team)", target_type="form")
    db.commit()
    return done


def main() -> None:
    company, url = for_tool(sys.argv)
    engine = make_engine(url)
    print(f"Company: {company}")
    upgrade(engine)
    with make_sessions(engine)() as db:
        for line in set_up(db):
            print(line)
    if "--quiet" not in sys.argv:
        print("Done. An administrator can change any of it in Settings > Forms and Settings > Customer types.")


if __name__ == "__main__":
    main()
