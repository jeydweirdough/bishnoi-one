"""Seeds the sales playbooks' KPIs and every division's scorecard (from
bishnoi-crm/data, read 2026-10-22): Hospital (CHC, DSC, Mentor), Rx field CHC,
MD Telesales (CHC, DSC), B2B CRR and NBD (CHC) and B2B DSC, B2C Online CHC,
2MG SCM CHC and Training Coach.

    uv run python -m app.tools.seed_scorecards [--company getmeds] [--dry-run]

Safe to run again: a KPI or scorecard already there (by its code) is brought
in line with the playbook, nothing is duplicated, targets and entries are
kept. Scorecards are matched to teams and roles by name; a missing one is
said, not made, except the Training team the Training Coach card needs.

Decided with the user on 2026-10-22:
- a sale is a Finance invoice sent or paid, by the salesperson on it;
- Hospital CHC weights are IST 50, DSO 25, HRR 15, NZSD 10 (the behaviour table);
- Rx doctors' NBD and CRR are MD Telesales'; the field Rx CHC keeps PAP, HIT,
  coverage and the gatekeeper set (Rx Team Training Playbook);
- every division is seeded, the 2MG and Training Coach KPIs entered by hand.

Points the playbooks leave out (bonus points above 100% or 110%) aren't
scored; a band's gap (60-61%) goes to the band above it.
"""

import argparse
import sys

from sqlalchemy import func, select

from app.audit import audit
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import Kpi, Role, Scorecard, Team
from app.tenants import for_tool

TOOL = "scorecard seed tool"

# --- the KPIs: measured from the CRM and Finance, or entered by hand each month ---------------
# code: (name, measure, filters, unit, better, description)
KPIS = {
    "ist": ("Sales invoiced (IST)", "invoiced", {}, "money", "higher", "Invoices sent or paid in the month, against the person's monthly target."),
    "nzsd": ("Sales days (NZSD)", "sale_days", {}, "percent", "higher", "Days with at least one invoice, out of the working days (Monday to Saturday)."),
    "nzsd_500": ("Sales days, ₱500 and up (NZSD)", "sale_days", {"minCentavos": 50000}, "percent", "higher", "Days with an invoice of at least ₱500, out of the working days (B2B)."),
    "crr": ("Customers kept (CRR/HRR)", "customers_kept", {}, "percent", "higher", "Customers invoiced last month and again this month, out of last month's."),
    "nbd": ("New accounts (NBD)", "new_accounts", {}, "count", "higher", "Customers invoiced for the first time this month, against the monthly quota."),
    "dso": ("Days sales outstanding (DSO)", "dso", {}, "count", "lower", "What customers owe, over a day's sales this month."),
    "ocr": ("Cancellation rate (OCR)", "cancel_rate", {}, "percent", "lower", "Invoices voided out of those made this month."),
    "pap": ("Assistance approved (PAP)", "assistance_approved", {}, "count", "higher", "Government assistance applications (DSWD, PCSO, OVP, YAKAP) approved this month."),
    "coverage": ("Doctors covered (CCF)", "doctors_visited", {}, "count", "higher", "Different doctors visited this month, out of the 80 in the territory."),
    # Entered by hand each month (Results, then Enter results).
    "hit": ("Formulary approvals (HIT)", "manual", {}, "count", "higher", "Hospital formulary (PTC) approvals for products in their launch year. Scored quarterly."),
    "pkt": ("Product knowledge test (PKT)", "manual", {}, "percent", "higher", "The month's product knowledge test score."),
    "bdc": ("Brand detailing compliance (BDC)", "manual", {}, "percent", "higher", "Calls detailing the 3 focus and 2 reminder brands, out of all calls."),
    "jfw": ("Joint field work score (JFW)", "manual", {}, "percent", "higher", "The DSC's average score over at least 2 days in the field with the CHC."),
    "dot": ("Tier 1 doctors seen 4 times (DOT)", "manual", {}, "percent", "higher", "Tier 1 doctors seen 4 times this month, out of all Tier 1 doctors."),
    "cross_sell": ("Cross-sell accounts", "manual", {}, "count", "higher", "Clients buying a product new to them in the last 6 months, against the quota."),
    "gpgr": ("Gross profit growth (GPGR)", "manual", {}, "percent", "higher", "Gross profit this month against last month's, as a percentage change."),
    "fulfilment": ("Orders fulfilled on time", "manual", {}, "percent", "higher", "Orders fulfilled the same day (Red Zone) or within 24 hours."),
    "compliance": ("Regulatory compliance points", "manual", {}, "count", "higher", "25 clean; 18 one minor GDP finding; 10 one major finding or a document lapse; 0 an S-2 or licence lapse."),
    "inventory_accuracy": ("Inventory accuracy", "manual", {}, "percent", "higher", "Counted stock that matches the records."),
    "gov_quote_2h": ("Government quotes within 2 hours", "manual", {}, "percent", "higher", "Government quotation requests answered within 2 hours."),
    "gl_6h": ("Guarantee letters within 6 hours", "manual", {}, "percent", "higher", "Guarantee-letter orders dispatched within 6 hours."),
    "sei": ("Sales enablement impact (SEI)", "manual", {}, "percent", "higher", "The trained group's sales against their target."),
    "cap": ("First-time pass rate (CAP)", "manual", {}, "percent", "higher", "Trainees passing at 80% or more on their first try."),
    "tca": ("Sessions on schedule (TCA)", "manual", {}, "percent", "higher", "Training sessions delivered on schedule."),
    "vac": ("Days to ramp up (VAC)", "manual", {}, "count", "lower", "Days for a new hire to reach 60% of target."),
    "gov": ("Governance deliverables (GOV)", "manual", {}, "count", "higher", "Of the 4 monthly governance deliverables, how many were done."),
}


def b(*pairs, lower=False):
    """Bands from (threshold, points) pairs, best first, then 0 for anything else."""
    key = "max" if lower else "min"
    return [{key: t, "points": p} for t, p in pairs] + [{"points": 0}]


def item(kpi, points, bands, on="value", **extra):
    return {"kpi": kpi, "points": points, "on": on, "bands": bands, **extra}


# The raises the playbooks give for the year's average score (shown against the month as a guide).
REP_BANDS = [
    {"min": 100, "label": "Distinguished", "raise": "35%", "pip": False},
    {"min": 95, "label": "Elite", "raise": "20%", "pip": False},
    {"min": 85, "label": "High performer", "raise": "10%", "pip": False},
    {"min": 75, "label": "Proficient", "raise": "6%", "pip": False},
    {"min": 60, "label": "Developing", "raise": "3%", "pip": False},
    {"min": 0, "label": "Below standard", "raise": "0%", "pip": True},
]
LEAD_BANDS = [
    {"min": 100, "label": "Distinguished", "raise": "20%", "pip": False},
    {"min": 95, "label": "Elite", "raise": "15%", "pip": False},
    {"min": 85, "label": "High performer", "raise": "10%", "pip": False},
    {"min": 75, "label": "Proficient", "raise": "6%", "pip": False},
    {"min": 60, "label": "Developing", "raise": "3%", "pip": False},
    {"min": 0, "label": "Below standard", "raise": "0%", "pip": True},
]

REPS = ("Salesperson", "Field agent", "Team Lead")
COACHES = ("District coach",)
MENTORS = ("Manager",)

# MD Telesales and B2C bands, shared.
MDT_CRR = b((95, 15), (85, 13), (75, 11), (65, 8))
MDT_NZSD = b((95, 15), (90, 13), (80, 11), (70, 8))
MDT_DSO = b((30, 15), (40, 11), (50, 7), (60, 3), lower=True)

# code: (name, teams, roles, items, bands, description)
CARDS = {
    "hos_chc": ("Hospital CHC", ("HOS",), REPS, [
        item("ist", 50, b((91, 50), (81, 40), (71, 30), (60, 20)), on="attainment", cap={"below": 60, "total": 40}),
        item("dso", 25, b((70, 25), (89, 15), lower=True)),
        item("crr", 15, b((95, 15), (85, 12), (75, 8)), label="Hospitals kept (HRR)"),
        item("nzsd", 10, b((95, 10), (90, 8), (80, 6), (70, 4))),
    ], REP_BANDS, "Hospital playbook: IST 50, DSO 25, HRR 15, NZSD 10 (the behaviour table's weights)."),
    "hos_dsc": ("Hospital DSC", ("HOS",), COACHES, [
        item("ist", 50, b((91, 50), (81, 40), (71, 30), (60, 20)), on="attainment", scope="team", label="District sales (DST)", cap={"below": 60, "total": 40}),
        item("dso", 25, b((70, 25), (89, 15), lower=True), scope="team"),
        item("ist", 15, b((81, 15), (61, 9)), on="attainment", scope="team_average", floorEach=60, label="Team target achievement (TTAR)"),
        item("crr", 10, b((85, 10), (75, 6)), scope="team", label="Hospitals kept (HRR)"),
    ], LEAD_BANDS, "Hospital DSC playbook: DST 50, DSO 25, TTAR 15, HRR 10."),
    "hos_mentor": ("Hospital Mentor", ("HOS",), MENTORS, [
        item("ist", 40, b((91, 40), (81, 34), (71, 28), (60, 20)), on="attainment", scope="team", label="National sales (NST)", cap={"below": 60, "total": 50}),
        item("dso", 20, b((70, 20), (89, 12), lower=True), scope="team"),
        item("ist", 20, b((81, 20), (61, 12)), on="attainment", scope="team_average", floorEach=60, label="Coach target achievement (CTAR)"),
        item("crr", 10, b((95, 10), (90, 8), (85, 6), (80, 4)), scope="team", label="Hospitals kept (HRR)"),
        item("gpgr", 10, b((10, 10), (6, 8), (3, 6), (0, 4))),
    ], LEAD_BANDS, "Hospital Mentor playbook: NST 40, DSO 20, CTAR 20, HRR 10, GPGR 10."),
    "rx_chc": ("Rx field CHC", ("Prescription Business",), REPS, [
        item("pap", 25, b((11, 25), (8, 23), (5, 20), (3, 15), (1, 10))),
        item("hit", 15, b((2, 15), (1, 10))),
        item("pkt", 10, b((80, 10)), group="gatekeeper", groupCap={"below": 40, "total": 70}),
        item("bdc", 10, b((90, 10)), group="gatekeeper"),
        item("jfw", 10, b((70, 10)), group="gatekeeper"),
        item("coverage", 10, b((80, 10)), on="attainment", of=80, group="gatekeeper", label="Total doctor coverage (TDC)", cap={"below": 80, "total": 70}),
        item("dot", 10, b((90, 10)), group="gatekeeper"),
    ], REP_BANDS, "Rx Team Training Playbook: sales, NBD and CRR are MD Telesales'; the field CHC keeps PAP, HIT and the gatekeeper set (out of 90)."),
    "mdt_chc": ("MD Telesales CHC", ("MD Telesales",), REPS, [
        item("ist", 40, b((91, 40), (81, 32), (71, 24), (60, 16)), on="attainment"),
        item("crr", 15, MDT_CRR),
        item("nbd", 15, b((81, 15), (66, 13), (51, 10), (36, 7), (20, 4)), on="attainment"),
        item("nzsd", 15, MDT_NZSD),
        item("dso", 15, MDT_DSO),
    ], REP_BANDS, "MD Telesales CHC playbook v1.1: IST 40, CRR 15, NBD 15, NZSD 15, DSO 15. Also owns Rx doctors' NBD and CRR."),
    "mdt_dsc": ("MD Telesales DSC", ("MD Telesales",), COACHES, [
        item("ist", 40, b((91, 40), (81, 32), (71, 24), (60, 16)), on="attainment", scope="team", label="District sales (DST)", cap={"below": 60, "total": 40}),
        item("crr", 20, b((95, 20), (85, 17), (75, 13), (65, 8)), scope="team"),
        item("nbd", 15, b((81, 15), (66, 13), (51, 10), (36, 7), (20, 4)), on="attainment", scope="team"),
        item("dso", 15, MDT_DSO, scope="team"),
        item("ist", 10, b((96, 10), (86, 9), (76, 7), (61, 4)), on="attainment", scope="team_average", floorEach=60, label="Team target achievement (TTAR)"),
    ], LEAD_BANDS, "MD Telesales DSC playbook: DST 40, CRR 20, NBD 15, DSO 15, TTAR 10."),
    "b2b_crr_chc": ("B2B CRR CHC", ("B2B CRR",), REPS, [
        item("ist", 30, b((90, 30), (75, 21), (60, 13)), on="attainment", cap={"below": 60, "total": 40}),
        item("crr", 30, b((95, 30), (85, 24), (75, 16))),
        item("dso", 20, b((70, 20), (89, 10), lower=True)),
        item("cross_sell", 10, b((100, 10), (75, 7), (50, 4)), on="attainment"),
        item("nzsd_500", 10, b((95, 10), (90, 8), (80, 6), (70, 4))),
    ], REP_BANDS, "B2B CHC playbook, CRR division: IST 30, CRR 30, DSO 20, cross-sell 10, NZSD 10 (invoices of ₱500 and up)."),
    "b2b_nbd_chc": ("B2B NBD CHC", ("B2B NBD",), REPS, [
        item("ist", 30, b((90, 30), (75, 21), (60, 13)), on="attainment", cap={"below": 60, "total": 40}),
        item("nbd", 30, b((100, 30), (75, 22), (50, 12)), on="attainment"),
        item("dso", 20, b((70, 20), (89, 10), lower=True)),
        item("crr", 10, b((95, 10), (85, 8), (75, 5))),
        item("nzsd_500", 10, b((95, 10), (90, 8), (80, 6), (70, 4))),
    ], REP_BANDS, "B2B CHC playbook, NBD division: IST 30, NBD 30, DSO 20, CRR 10, NZSD 10 (invoices of ₱500 and up)."),
    "b2b_dsc": ("B2B DSC", ("B2B",), COACHES, [
        item("ist", 40, b((90, 40), (75, 26), (60, 16)), on="attainment", scope="team", label="District sales (DST)", cap={"below": 60, "total": 30}),
        item("dso", 20, b((70, 20), (89, 10), lower=True), scope="team"),
        item("ist", 20, b((81, 20), (60, 12)), on="attainment", scope="team_average", floorEach=60, label="Team target achievement (TTAR)"),
        item("crr", 10, b((95, 10), (85, 8), (75, 5)), scope="team"),
        item("nbd", 10, b((100, 10), (75, 7), (50, 4)), on="attainment", scope="team"),
    ], LEAD_BANDS, "B2B DSC playbook: DST 40, DSO 20, TTAR 20, CRR 10, NBD 10."),
    "b2c_chc": ("B2C Online CHC", ("B2C",), REPS, [
        item("ist", 45, b((91, 45), (81, 36), (71, 27), (60, 18)), on="attainment", cap={"below": 60, "total": 40}),
        item("crr", 15, MDT_CRR),
        item("nbd", 15, b((81, 15), (66, 13), (51, 10), (36, 7), (20, 4)), on="attainment"),
        item("nzsd", 15, MDT_NZSD),
        item("ocr", 10, b((0.99, 10), (4, 8), (9, 5), (14, 2), lower=True)),
    ], REP_BANDS, "B2C Online CHC playbook v1.3: IST 45, CRR 15, NBD 15, NZSD 15, OCR 10."),
    "scm_chc": ("2MG SCM CHC", ("2MG SCM",), REPS, [
        item("fulfilment", 25, b((98, 25), (95, 22), (90, 18), (80, 10))),
        item("compliance", 25, b((25, 25), (18, 18), (10, 10))),
        item("inventory_accuracy", 20, b((99, 20), (98, 17), (97, 14), (95, 8))),
        item("gov_quote_2h", 15, b((95, 15), (90, 10), (80, 6))),
        item("gl_6h", 15, b((95, 15), (90, 10), (80, 6))),
    ], REP_BANDS, "2MG SCM CHC playbook v3: fulfilment 25, compliance 25, inventory accuracy 20, quotes in 2 h 15, guarantee letters in 6 h 15."),
    "training_coach": ("Training Coach", ("Training",), (), [
        item("sei", 35, b((100, 35), (90, 28), (75, 22), (60, 15)), cap={"below": 60, "total": 55}),
        item("cap", 25, b((95, 25), (85, 21), (75, 16), (60, 10))),
        item("tca", 20, b((100, 20), (90, 17), (80, 13), (70, 8))),
        item("vac", 10, b((30, 10), (45, 8), (60, 5), lower=True)),
        item("gov", 10, b((4, 10), (3, 8), (2, 5))),
    ], LEAD_BANDS, "Training Coach playbook: SEI 35, CAP 25, TCA 20, VAC 10, GOV 10. Below 60 for 2 months: an HR review."),
}


def seed(db, dry_run: bool = False) -> list[str]:
    said: list[str] = []
    teams = {t.name: t for t in db.scalars(select(Team))}
    roles = {r.name: r for r in db.scalars(select(Role))}
    if "Training" not in teams:
        said.append("Team Training: made (the Training Coach scorecard is for its people).")
        if not dry_run:
            teams["Training"] = Team(name="Training", description="Training coaches (Training Coach scorecard).", headquarters=[])
            db.add(teams["Training"])
            db.flush()
    top = (db.scalar(select(func.max(Kpi.sort_order))) or 0) + 1
    for n, (code, (name, measure, filters, unit, better, about)) in enumerate(KPIS.items()):
        k = db.scalar(select(Kpi).where(Kpi.code == code))
        if k is None:
            clash = db.scalar(select(Kpi).where(Kpi.name == name))
            k = clash or Kpi(code=code, sort_order=top + n, roles=[])
            said.append(f"KPI {name}: {'given its code' if clash else 'added'}.")
            k.code = code
        k.name, k.measure, k.filters, k.unit, k.better, k.description, k.is_active = name, measure, filters, unit, better, about, True
        if not dry_run:
            db.add(k)
    for n, (code, (name, team_names, role_names, items, bands, about)) in enumerate(CARDS.items()):
        missing = [t for t in team_names if t not in teams] + [r for r in role_names if r not in roles]
        if missing:
            said.append(f"Scorecard {name}: no {', '.join(missing)} here; it won't match anyone until there is.")
        c = db.scalar(select(Scorecard).where(Scorecard.code == code)) or Scorecard(code=code)
        said.append(f"Scorecard {name}: {'updated' if c.id else 'added'}.")
        c.name, c.description, c.items, c.bands, c.sort_order, c.is_active = name, about, items, bands, n, True
        c.teams = [teams[t].id for t in team_names if t in teams and teams[t].id]
        c.roles = [roles[r].id for r in role_names if r in roles]
        if not dry_run:
            db.add(c)
    if not dry_run:
        audit(db, TOOL, "scorecards.seeded", target=f"{len(KPIS)} KPIs, {len(CARDS)} scorecards", target_type="kpi")
    return said


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # the peso sign, on a Windows console
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--company", help="the company's short name (its own database), e.g. getmeds")
    parser.add_argument("--dry-run", action="store_true", help="say what would be done, change nothing")
    args = parser.parse_args()
    company, url = for_tool(sys.argv)
    engine = make_engine(url)
    upgrade(engine)
    print(f"Company: {company}")
    with make_sessions(engine)() as db:
        for line in seed(db, args.dry_run):
            print(line)
        if args.dry_run:
            db.rollback()
            print("Dry run: nothing was changed.")
        else:
            db.commit()
            print(f"Done: {len(KPIS)} KPIs and {len(CARDS)} scorecards are in line with the playbooks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
