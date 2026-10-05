"""The customer forms of HOS (Ma'am Van), B2B and BID (Sir Subhir), on top of
the Rx team's (app/tools/rx_form.py, run first). Set up once; safe to run again.

    uv run python -m app.tools.division_forms

Only what helps them sell and follow up (see the CRM decisions):
- HOS, cancer care: hospitals and cancer centers (cancer patients a month,
  cancer types treated, our products on their formulary), and oncologists,
  pharmacists and purchase heads, profiled as Rx profiles its doctors;
- B2B, distribution: distributors, drugstore chains and wholesalers (TIN for
  Finance's invoices, region, credit terms, monthly volume, our products carried);
- BID, government buying: government hospitals, DOH offices and LGUs
  (procurement office, PhilGEPS reference, region). The bids themselves are deals.
Industry, lead source and country aren't asked of them (lead source is B2C's).
"""

import sys
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import make_engine, make_sessions
from app.tenants import for_tool
from app.migrate import upgrade
from app.models import Company, CustomerType, FormField, FormSection, Team
from app import clidp
from app.tools import rx_form

TOOL = "division forms tool"
GENERAL_TYPES = rx_form.GENERAL_TYPES

# Each division's own customer types: (code, name).
TYPES = {
    "HOS": [("hospital", "Hospital"), ("cancer_center", "Cancer center"), ("oncologist", "Oncologist"), ("pharmacist", "Pharmacist"), ("purchase_head", "Purchase head")],
    "B2B": [("distributor", "Distributor"), ("drugstore_chain", "Drugstore chain"), ("wholesaler", "Wholesaler")],
    "BID": [("government_hospital", "Government hospital"), ("doh_office", "DOH office"), ("lgu", "LGU")],
}

CANCER_TYPES = ["Breast", "Lung", "Colorectal", "Prostate", "Cervical", "Ovarian", "Liver", "Gastric", "Leukemia", "Lymphoma", "Multiple myeloma", "Other"]
CREDIT_TERMS = ["Cash on delivery", "15 days", "30 days", "45 days", "60 days", "90 days"]

# Fields of their own: (division, section, key, label, type, settings). "types": whom it's asked of.
FIELDS = [
    ("HOS", "Oncology profile", "x_cancer_patients", "Cancer patients a month", "number", {"types": ["hospital", "cancer_center"], "help_text": "About how many cancer patients they treat a month."}),
    ("HOS", "Oncology profile", "x_cancer_types", "Cancer types treated", "multi_choice", {"types": ["hospital", "cancer_center"], "options": CANCER_TYPES}),
    ("HOS", "Oncology profile", "x_formulary", "Our products on their formulary", "products", {"types": ["hospital", "cancer_center"]}),
    ("B2B", "The customer", "tin", "TIN", "text", {"help_text": "On Finance's invoices to them."}),
    ("B2B", "The customer", "x_credit_terms", "Credit terms", "choice", {"options": CREDIT_TERMS}),
    ("B2B", "Trade profile", "x_monthly_volume", "Monthly volume", "money", {"help_text": "About how much they buy from us a month, in pesos."}),
    ("B2B", "Trade profile", "x_products_carried", "Our products they carry", "products", {}),
    ("BID", "The customer", "x_procurement_office", "Procurement office", "text", {"help_text": "The office that runs their bids (BAC secretariat, supply office)."}),
    ("BID", "The customer", "x_philgeps", "PhilGEPS reference", "text", {"help_text": "Their number on PhilGEPS, to find their bid notices."}),
]

# The Rx form's fields these divisions share, and for which of them.
SHARED = {"x_region": ["HOS", "B2B", "BID"], "x_landline": ["HOS", "B2B", "BID"], "x_potential": ["HOS", "B2B", "BID"]}
# Rx's people fields (department, qualification, hospital, personal) and doctor
# profile: HOS's oncologists, pharmacists and purchase heads get them too.
PEOPLE_FIELDS = ["x_department", "x_qualification", "x_hospital", "x_gender", "x_marital_status", "x_birth_date", "x_anniversary", "x_interests"]
DOCTOR_FIELDS = [key for _, key, *_ in rx_form.FIELDS if key.startswith(("x_patients_per_day", "x_product_interest", "x_molecule"))]
HOS_PEOPLE = ["oncologist", "pharmacist", "purchase_head"]

NOT_FOR_THEM = ("industry", "leadSource", "country")
# What a person's hospital can be.
HOSPITAL_TYPES = ("hospital", "cancer_center", "government_hospital", "dialysis_center")


def section(db: Session, sections: dict, title: str) -> FormSection:
    if title not in sections:
        last = max((s.sort_order for s in sections.values()), default=0)
        sections[title] = FormSection(entity="company", title=title, columns=2, sort_order=last + 1)
        db.add(sections[title])
        db.flush()
    return sections[title]


def set_up(db: Session) -> list[str]:
    teams = {t.name.upper(): t.id for t in db.scalars(select(Team))}
    have = {d: teams[d] for d in TYPES if d in teams}
    if not have:
        raise SystemExit("None of HOS, B2B and BID are here yet. Add them in People and access > Teams first.")
    done: list[str] = []
    add = rx_form.add_to
    sections = {s.title: s for s in db.scalars(select(FormSection).where(FormSection.entity == "company"))}
    fields = {f.key: f for f in db.scalars(select(FormField).where(FormField.entity == "company"))}

    for division, title, key, label, kind, more in FIELDS:
        if division not in have:
            continue
        field = fields.get(key)
        if field is None:
            where = section(db, sections, title)
            here = [f.sort_order for f in fields.values() if f.section_id == where.id]
            field = FormField(
                entity="company", key=key, label=label, type=kind, standard=False, locked=False,
                options=list(more.get("options", [])), option_names={}, unique=False,
                help_text=more.get("help_text"), section_id=where.id, sort_order=max(here, default=0) + 1,
            )
            db.add(field)
            fields[key] = field
            done.append(f"Added {label} ({division})")
        field.only_teams = add(field.only_teams, [have[division]])
        if more.get("types") and not field.only_types and not field.except_types:
            field.only_types = list(more["types"])

    for key, divisions in SHARED.items():
        if key in fields:
            fields[key].only_teams = add(fields[key].only_teams, [have[d] for d in divisions if d in have])
    if "HOS" in have:
        for key in [*PEOPLE_FIELDS, *DOCTOR_FIELDS]:
            field = fields.get(key)
            if field is None:
                continue
            field.only_teams = add(field.only_teams, [have["HOS"]])
            # Only widen a type list Rx set; an empty one already means every type.
            if field.only_types:
                kinds = HOS_PEOPLE if key in PEOPLE_FIELDS else ["oncologist"]
                field.only_types = add(field.only_types, kinds)
        done.append("HOS oncologists, pharmacists and purchase heads get the Rx people and doctor profile fields")
    for key in NOT_FOR_THEM:
        if key in fields:
            fields[key].except_teams = add(fields[key].except_teams, list(have.values()))
    done.append("Kept industry, lead source and country off the HOS, B2B and BID forms")

    types = {t.code: t for t in db.scalars(select(CustomerType))}
    order = max((t.sort_order for t in types.values()), default=0)
    for division, offered in TYPES.items():
        if division not in have:
            continue
        for code, name in offered:
            kind = types.get(code)
            if kind is None:
                if db.scalar(select(CustomerType.code).where(func.lower(CustomerType.name) == name.lower())):
                    continue
                order += 1
                kind = CustomerType(code=code, name=name, color="blue", sort_order=order, is_active=True, only_teams=[], except_teams=[])
                db.add(kind)
                types[code] = kind
                done.append(f"Added the {name} type")
            kind.only_teams = add(kind.only_teams, [have[division]])
    for code in GENERAL_TYPES:
        if code in types:
            types[code].except_teams = add(types[code].except_teams, list(have.values()))
    done.append("Kept Prospect, Customer, Partner and Inactive off their type lists")

    # A person's hospital becomes a link to the hospital as a customer, so Rx
    # and HOS see the same hospital from both sides. Only while nothing was
    # typed in it: typed names stay as they are.
    hospital = fields.get("x_hospital")
    if hospital is not None and hospital.type == "text":
        typed = any((extra or {}).get("x_hospital") for (extra,) in db.execute(select(Company.extra)))
        if typed:
            done.append("Kept Hospital name as typed text: some customers already have one typed in")
        else:
            hospital.type, hospital.options = "customer", list(HOSPITAL_TYPES)
            hospital.help_text = "The hospital they work at, picked from the CRM's customers. Not there yet? Add it as a customer first."
            done.append("Hospital name now links to the hospital, as a customer")

    # Each product's CLIDP (app/clidp.py): its number and how long it's valid.
    product = {f.key: f for f in db.scalars(select(FormField).where(FormField.entity == "product"))}
    product_sections = {s.title: s for s in db.scalars(select(FormSection).where(FormSection.entity == "product"))}
    for key, label, kind, hint in (
        (clidp.NUMBER, "CLIDP number", "text", "The FDA's Certificate of Listing of Identical Drug Product."),
        (clidp.VALID_UNTIL, "CLIDP valid until", "date", "Quotes and bids warn once it has run out."),
    ):
        if key not in product:
            if "Regulatory" not in product_sections:
                last = max((s.sort_order for s in product_sections.values()), default=0)
                product_sections["Regulatory"] = FormSection(entity="product", title="Regulatory", columns=2, sort_order=last + 1)
                db.add(product_sections["Regulatory"])
                db.flush()
            db.add(FormField(entity="product", key=key, label=label, type=kind, standard=False, locked=False, options=[], option_names={}, help_text=hint,
                             section_id=product_sections["Regulatory"].id, sort_order=len(product) + 1))
            product[key] = True
            done.append(f"Added {label} to the product form")

    audit(db, TOOL, "form.updated", target="company form (HOS, B2B, BID)", target_type="form")
    db.commit()
    return done


def main() -> None:
    company, url = for_tool(sys.argv)
    engine = make_engine(url)
    print(f"Company: {company}")
    upgrade(engine)
    with make_sessions(engine)() as db:
        for line in rx_form.set_up(db):
            print(line)
        for line in set_up(db):
            print(line)
    print("Done. An administrator can change any of it in Settings > Forms and Settings > Customer types.")


if __name__ == "__main__":
    main()
