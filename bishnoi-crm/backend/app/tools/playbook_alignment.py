"""Configures Bishnoi CRM to align with the commercial sales playbooks (Hospital,
Rx, MD Telesales, B2B, B2C, SCM).

Run once:
    .venv/Scripts/python -m app.tools.playbook_alignment

Safe to run repeatedly (idempotent: does not duplicate existing fields or settings).
"""

import sys
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import make_engine, make_sessions
from app.tenants import for_tool
from app.migrate import upgrade
from app.models import AttentionRule, FormField, FormSection, SalesSettings, Team

TOOL = "playbook alignment tool"

COMPANY_FIELDS = [
    ("The customer", "x_tier", "Account Tier", "choice", {
        "options": ["Tier 1 (Core)", "Tier 2 (Growth)", "Tier 3 (Maintenance)"],
        "help_text": "Account prioritization tier based on revenue potential and call frequency standard."
    }),
    ("The customer", "x_pvi_zone", "PVI Velocity Zone", "choice", {
        "options": ["Red (Peak / Tender <72h)", "Yellow (High Liquidity)", "Green (Stable Maintenance)"],
        "help_text": "Prescription / Purchasing Velocity zone assigned weekly for routing priority."
    }),
    ("The customer", "x_pdea_s2", "PDEA S-2 License No.", "text", {
        "help_text": "PDEA S-2 narcotic handling license number for Schedule II controlled substances."
    }),
    ("The customer", "x_s2_expiry", "S-2 License Expiry Date", "date", {
        "help_text": "Audited every 30 days. Pitching narcotics is prohibited if license is expired."
    }),
    ("The customer", "x_credit_status", "Credit Status", "choice", {
        "options": ["Good Standing", "Approaching Due (Day 25)", "Overdue (Day 31+)", "Suspended (>90 Days)"],
        "help_text": "Credit health status. Overdue accounts above 90 days freeze discount and credit authorization."
    }),
    ("The customer", "x_account_lifecycle", "Account Lifecycle Status", "choice", {
        "options": ["Prospect", "Active", "CRR-Eligible (3+ mos)", "Lapsed – NBD Reassignment", "Cold Lead"],
        "help_text": "Account lifecycle track for B2B and institutional clients."
    }),
]

CONTACT_FIELDS = [
    ("The person", "x_stakeholder", "Stakeholder Classification", "choice", {
        "options": [
            "Hospital CFO / COO",
            "Procurement Director / Purchasing Officer",
            "BAC Chairman / BAC Secretariat",
            "Pharmacy Director / Chief Pharmacist",
            "Finance Officer / Accounts Payable",
            "Warehouse Manager / Supply Officer",
            "Malasakit Desk Officer / MAIFIP Coordinator",
            "Department Head with Budget Authority",
            "OR Head / OR Nurse Supervisor",
            "Blood Bank Head",
            "Dialysis Centre Head",
            "Other Stakeholder"
        ],
        "help_text": "Stakeholder role in procurement, clinical prescribing, or payment approval."
    }),
    ("The person", "x_care_team_status", "Care Team Group Status", "choice", {
        "options": ["Active", "Not Yet Created", "Patient Declined", "Archived"],
        "help_text": "Viber/WhatsApp Patient or Doctor Care Team status."
    }),
]

QUOTE_FIELDS = [
    ("More about this quote", "x_payer_program", "Assistance Program / Payer", "choice", {
        "options": [
            "Direct / Cash",
            "PCSO IMAP",
            "DSWD AICS",
            "OVP",
            "DOH-MAIFIP / Malasakit",
            "YAKAP / GAMOT",
            "Private Health Insurance"
        ],
        "help_text": "Government assistance fund or payer backing this quotation."
    }),
    ("More about this quote", "x_procurement_mode", "Procurement Modality (RA 9184)", "choice", {
        "options": [
            "Shopping (Sec 52)",
            "Small Value Procurement (Sec 53.9)",
            "Direct Contracting (Sec 50)",
            "Emergency Cases (Sec 53.2)",
            "Public Bidding (Sec 10)",
            "Consignment"
        ],
        "help_text": "RA 9184 public procurement modality for government tenders."
    }),
    ("More about this quote", "x_gl_number", "Guarantee Letter (GL) No.", "text", {
        "help_text": "Guarantee letter or voucher reference number from government agency."
    }),
    ("More about this quote", "x_gl_expiry", "GL Validity Date", "date", {
        "help_text": "Expiration date of the Guarantee Letter."
    }),
    ("More about this quote", "x_csp_number", "CSP Permit No.", "text", {
        "help_text": "FDA Compassionate Special Permit reference number."
    }),
]

DEAL_SOURCES = [
    "Field Visit / Doctor Detailing",
    "Doctor Referral (Patient)",
    "Prescription CHC Referral",
    "Hospital Cold Call",
    "PhilGEPS Tender Notice",
    "Pharmacy Inbound / Counter",
    "Website / Facebook Care Team",
    "Other"
]

DEAL_LOST_REASONS = [
    "Competitor Lower Price",
    "Missing / Expired PDEA S-2 License",
    "Formulary Inclusion Rejected by P&T",
    "Disqualified by BAC / Incomplete Bidding Docs",
    "Hospital Budget / Procurement Frozen",
    "Out of Stock / Delivery TAT Cannot Be Met",
    "Credit Terms Rejected (>90 DSO lock)",
    "Other"
]


def ensure_section(db: Session, entity: str, title: str) -> FormSection:
    sec = db.scalar(select(FormSection).where(FormSection.entity == entity, FormSection.title == title))
    if sec is None:
        last = db.scalar(select(func.max(FormSection.sort_order)).where(FormSection.entity == entity)) or 0
        sec = FormSection(entity=entity, title=title, columns=2, sort_order=last + 1)
        db.add(sec)
        db.flush()
    return sec


def apply_fields(db: Session, entity: str, field_defs: list[tuple]) -> list[str]:
    done = []
    fields = {f.key: f for f in db.scalars(select(FormField).where(FormField.entity == entity))}
    for title, key, label, kind, more in field_defs:
        field = fields.get(key)
        if field is None:
            sec = ensure_section(db, entity, title)
            here = [f.sort_order for f in fields.values() if f.section_id == sec.id]
            opts = more.get("options", [])
            field = FormField(
                entity=entity,
                key=key,
                label=label,
                type=kind,
                standard=False,
                locked=False,
                options=opts if isinstance(opts, list) else list(opts),
                option_names={o: n for o, n in opts.items() if n} if isinstance(opts, dict) else {},
                unique=more.get("unique", False),
                help_text=more.get("help_text"),
                placeholder=more.get("placeholder"),
                section_id=sec.id,
                sort_order=max(here, default=0) + 1,
            )
            db.add(field)
            fields[key] = field
            done.append(f"Added {entity} field: {label} ({key})")
        else:
            # Update options or help text if empty
            if more.get("options") and not field.options:
                opts = more["options"]
                field.options = opts if isinstance(opts, list) else list(opts)
                done.append(f"Updated options for {label}")
            if more.get("help_text") and not field.help_text:
                field.help_text = more["help_text"]
    return done


def set_up(db: Session) -> list[str]:
    done: list[str] = []

    # 1. Ensure Teams (MD Telesales & 2MG SCM)
    teams = {t.name.upper(): t for t in db.scalars(select(Team))}
    if "MD TELESALES" not in teams and "TELESALES" not in teams:
        t = Team(name="MD Telesales", description="Inside sales to physicians and chronic patients", is_active=True, share_customers=True)
        db.add(t)
        db.flush()
        teams["MD TELESALES"] = t
        done.append("Created team: MD Telesales")
    if "2MG SCM" not in teams and "SCM" not in teams:
        t = Team(name="2MG SCM", description="Central order fulfillment hub and branch pharmacy operations", is_active=True, share_customers=False)
        db.add(t)
        db.flush()
        teams["2MG SCM"] = t
        done.append("Created team: 2MG SCM")

    # 2. Add Custom Form Fields
    done.extend(apply_fields(db, "company", COMPANY_FIELDS))
    done.extend(apply_fields(db, "contact", CONTACT_FIELDS))
    done.extend(apply_fields(db, "quote", QUOTE_FIELDS))

    # 3. Update SalesSettings deal lists and retention defaults
    settings_row = db.get(SalesSettings, 1) or SalesSettings(id=1)
    if not settings_row.deal_lists:
        settings_row.deal_lists = {
            "sources": DEAL_SOURCES,
            "lostReasons": DEAL_LOST_REASONS,
        }
        done.append("Configured deal sources and lost reasons in Sales Settings")
    else:
        # Merge our sources and lost reasons
        curr = dict(settings_row.deal_lists)
        sources = list(dict.fromkeys(curr.get("sources", []) + DEAL_SOURCES))[:50]
        reasons = list(dict.fromkeys(curr.get("lostReasons", []) + DEAL_LOST_REASONS))[:50]
        settings_row.deal_lists = {"sources": sources, "lostReasons": reasons}
        done.append("Enriched deal sources and lost reasons")

    settings_row.allows_guarantee_letters = True
    settings_row.at_risk_days = 30
    settings_row.lost_days = 90
    db.add(settings_row)

    # 4. Set Attention Rules per Team
    # Default rule for everyone (team_id=None)
    rules = {r.team_id: r for r in db.scalars(select(AttentionRule))}
    if None not in rules:
        r = AttentionRule(team_id=None, quiet_days=30, notice_days=7, clidp_days=30, stuck_days=2)
        db.add(r)
        rules[None] = r
        done.append("Configured default company attention rule (30d quiet, 2d stuck)")

    # Per-team rules
    rules_map = {
        "HOS": (14, 1),        # Hospital: 14d quiet, 1d stuck (urgent tenders)
        "B2B": (20, 2),        # B2B: 20d quiet, 2d stuck
        "B2C": (25, 1),        # B2C: 25d quiet (refill cycle), 1d stuck
        "MD TELESALES": (20, 2), # Telesales: 20d quiet, 2d stuck
        "STC": (21, 2),        # Rx STC: 21d quiet (3-week doctor lapse)
        "B&B": (21, 2),        # Rx B&B: 21d quiet
        "URO": (21, 2),        # Rx URO: 21d quiet
    }
    for t_name, (quiet, stuck) in rules_map.items():
        team = teams.get(t_name)
        if team and team.id not in rules:
            r = AttentionRule(team_id=team.id, quiet_days=quiet, notice_days=7, clidp_days=30, stuck_days=stuck)
            db.add(r)
            rules[team.id] = r
            done.append(f"Configured attention rule for {team.name}: {quiet}d quiet, {stuck}d stuck quote")

    audit(db, TOOL, "playbook.aligned", target="playbook configuration alignment", target_type="config")
    db.commit()
    return done


def main() -> None:
    company, url = for_tool(sys.argv)
    engine = make_engine(url)
    print(f"Company: {company}")
    upgrade(engine)
    with make_sessions(engine)() as db:
        for line in set_up(db):
            print(" -", line)
    print("Done! The CRM configuration is now aligned with the sales department playbooks.")


if __name__ == "__main__":
    main()
