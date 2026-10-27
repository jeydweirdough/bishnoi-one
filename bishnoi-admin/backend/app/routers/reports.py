"""Executive Admin's reports (decided 2026-10-25, benchmarks/surpass.md §11): one registry, each
report in a group (Compliance, Fleet and travel, Service requests, Marketing) and needing the view
permission for its data, drawn by the one app's shared report kit (src/platform/reports/).

- GET /admin/reports: the reports this person may open.
- GET /admin/reports/{key}?from&to: one report: columns, rows, headline figures, chart.

Renewal reports look ahead: with no period asked for they cover today and the next 90 days.
Admin keeps amounts in pesos; the kit reads money in centavos, so they're sent as centavos.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import Access, CurrentAccess
from app.deps import DB, SettingsDep
from app.models import (
    ComplianceRecord,
    CorporateDocument,
    DeviceIssue,
    FleetCard,
    ImmigrationRecord,
    PromoDistribution,
    PromoMaterial,
    PromoProduction,
    PropertyRecord,
    Ticket,
    TravelSponsorship,
    Vehicle,
)

router = APIRouter(prefix="/admin/reports", tags=["reports"])

DOCUMENT_TYPES = {"visa": "Visa", "acr_card": "ACR I-Card", "aep_permit": "DOLE AEP", "passport": "Passport", "exec_id": "Executive ID"}
CLOSED_TICKETS = ("resolved", "closed")


def words(code: str | None) -> str:
    """A stored code as words: pending_renewal is Pending renewal."""
    return (code or "").replace("_", " ").capitalize()


def aware(moment: datetime) -> datetime:
    """SQLite hands stored moments back without their zone; they were saved in UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=ZoneInfo("UTC"))


def centavos(pesos: float | None) -> int | None:
    return None if pesos is None else round(pesos * 100)


def col(key: str, label: str, kind: str = "text") -> dict:
    return {"key": key, "label": label, "kind": kind}


def fig(label: str, value, kind: str = "number", tone: str | None = None) -> dict:
    return {"label": label, "value": value, "kind": kind, **({"tone": tone} if tone else {})}


def bar(x: str, *series: str) -> dict:
    return {"kind": "bar", "x": x, "series": list(series)}


@dataclass
class Ctx:
    db: Session
    zone: ZoneInfo
    today: date
    first: date
    last: date

    def day(self, moment: datetime | date | None) -> date | None:
        """A stored moment as the company's own day."""
        if moment is None or not isinstance(moment, datetime):
            return moment
        return aware(moment).astimezone(self.zone).date()

    def within(self, moment: datetime | date | None) -> bool:
        d = self.day(moment)
        return d is not None and self.first <= d <= self.last


@dataclass
class Report:
    key: str
    title: str
    group: str
    about: str
    build: Callable[[Ctx], tuple]
    needs: tuple[str, ...]
    dated: bool = True
    ahead: bool = False  # a renewal report: the period runs from today forward
    fixed: bool = False


# --- Compliance -------------------------------------------------------------------------------------


def _renewals(c: Ctx, access: Access) -> list[dict]:
    """Everything with a renewal date: permits, expatriates' papers, documents, leases."""
    out: list[dict] = []
    if access.can("permits.view"):
        for r in c.db.scalars(select(ComplianceRecord)):
            out.append({"kind": "Permit", "record": r.title, "reference": r.reference_number, "party": r.agency, "due": c.day(r.expiration_date), "status": words(r.status),
                        "owner": r.responsible_person or "", "cost": centavos(r.estimated_cost), "closed": r.status == "expired"})
    if access.can("immigration.view"):
        for r in c.db.scalars(select(ImmigrationRecord)):
            out.append({"kind": DOCUMENT_TYPES.get(r.document_type, words(r.document_type)), "record": r.individual_name, "reference": r.document_number, "party": r.nationality,
                        "due": c.day(r.expiration_date), "status": words(r.status), "owner": r.assigned_assistant or "", "cost": None, "closed": r.status == "expired_closed"})
    if access.can("documents.view"):
        for r in c.db.scalars(select(CorporateDocument).where(CorporateDocument.expiration_date.is_not(None))):
            out.append({"kind": words(r.category), "record": r.title, "reference": r.reference_number or "", "party": r.counterparty, "due": c.day(r.expiration_date),
                        "status": words(r.status), "owner": r.custodian or "", "cost": centavos(r.annual_value), "closed": r.status in ("terminated", "renewed")})
    if access.can("properties.view"):
        for r in c.db.scalars(select(PropertyRecord)):
            out.append({"kind": "Lease", "record": r.name, "reference": "", "party": r.lessor_name, "due": c.day(r.lease_end), "status": words(r.status),
                        "owner": r.assigned_manager or "", "cost": centavos(r.monthly_rent), "closed": r.status == "terminated"})
    return [r for r in out if not r["closed"] and r["due"] is not None]


RENEWAL_COLUMNS = [col("due", "Due", "date"), col("days", "Days left", "number"), col("kind", "Type"), col("record", "Record"), col("reference", "Reference"),
                   col("party", "Agency or party"), col("status", "Status"), col("owner", "Responsible")]


def _renewal_rows(c: Ctx, rows: list[dict]) -> list[dict]:
    rows.sort(key=lambda r: r["due"])
    return [{**{k: v for k, v in r.items() if k not in ("closed", "cost")}, "due": r["due"].isoformat(), "days": (r["due"] - c.today).days} for r in rows]


def renewals_due(access: Access):
    def build(c: Ctx):
        rows = _renewal_rows(c, [r for r in _renewals(c, access) if c.first <= r["due"] <= c.last])
        soon = sum(1 for r in rows if r["days"] <= 30)
        return (RENEWAL_COLUMNS, rows, [fig("Due in the period", len(rows)), fig("Within 30 days", soon, tone="warn" if soon else "good")], None)

    return build


def expired_records(access: Access):
    def build(c: Ctx):
        rows = _renewal_rows(c, [r for r in _renewals(c, access) if r["due"] < c.today])
        return (RENEWAL_COLUMNS, rows, [fig("Expired and not closed", len(rows), tone="bad" if rows else "good")], None)

    return build


def permits_by_agency(c: Ctx):
    by: dict[str, dict] = defaultdict(lambda: {"count": 0, "active": 0, "renewing": 0, "expired": 0, "cost": 0})
    for r in c.db.scalars(select(ComplianceRecord)):
        a = by[r.agency]
        a["count"] += 1
        expired = c.day(r.expiration_date) < c.today
        a["expired" if expired else "renewing" if r.status in ("pending_renewal", "under_review") else "active"] += 1
        a["cost"] += centavos(r.estimated_cost) or 0
    rows = [{"agency": k, **v} for k, v in sorted(by.items())]
    return (
        [col("agency", "Agency"), col("count", "Permits", "number"), col("active", "Active", "number"), col("renewing", "In renewal", "number"), col("expired", "Expired", "number"), col("cost", "Renewal cost", "money")],
        rows,
        [fig("Permits", sum(r["count"] for r in rows)), fig("Expired", sum(r["expired"] for r in rows), tone="bad" if any(r["expired"] for r in rows) else "good"),
         fig("Renewal cost", sum(r["cost"] for r in rows), "money")],
        bar("agency", "active", "renewing", "expired"),
    )


def leases(c: Ctx):
    rows = []
    for p in c.db.scalars(select(PropertyRecord).where(PropertyRecord.status != "terminated")):
        end = c.day(p.lease_end)
        rows.append({"property": p.name, "type": words(p.property_type), "lessor": p.lessor_name, "end": end.isoformat(), "days": (end - c.today).days,
                     "notice": (end - timedelta(days=p.notice_deadline_days)).isoformat(), "rent": centavos(p.monthly_rent), "deposit": centavos(p.security_deposit), "status": words(p.status)})
    rows.sort(key=lambda r: r["end"])
    rent = sum(r["rent"] or 0 for r in rows)
    late = sum(1 for r in rows if r["notice"] <= c.today.isoformat())
    return (
        [col("property", "Property"), col("type", "Type"), col("lessor", "Lessor"), col("end", "Lease ends", "date"), col("days", "Days left", "number"), col("notice", "Notice by", "date"),
         col("rent", "Monthly rent", "money"), col("deposit", "Deposit", "money"), col("status", "Status")],
        rows,
        [fig("Leases", len(rows)), fig("Monthly rent", rent, "money"), fig("Past the notice date", late, tone="warn" if late else "good")],
        None,
    )


# --- Fleet and travel -------------------------------------------------------------------------------


def vehicle_dues(c: Ctx):
    rows = []
    for v in c.db.scalars(select(Vehicle)):
        for what, due in (("Registration", v.registration_due), ("Insurance", v.insurance_due), ("Maintenance", v.pms_due)):
            if due and due <= c.last and (due >= c.first or due < c.today):
                rows.append({"due": due.isoformat(), "days": (due - c.today).days, "what": what, "vehicle": v.name, "plate": v.plate or "", "holder": v.owner_name or ""})
    rows.sort(key=lambda r: r["due"])
    overdue = sum(1 for r in rows if r["days"] < 0)
    return (
        [col("due", "Due", "date"), col("days", "Days left", "number"), col("what", "Due for"), col("vehicle", "Vehicle"), col("plate", "Plate"), col("holder", "Assigned to")],
        rows,
        [fig("Due", len(rows)), fig("Overdue", overdue, tone="bad" if overdue else "good")],
        None,
    )


def fuel_cards(c: Ctx):
    cards = list(c.db.scalars(select(FleetCard).order_by(FleetCard.holder_name)))
    rows = [{"holder": f.holder_name, "company": f.company_name or "", "plate": f.plate or f.conduction_sticker or "", "fuel": f.fuel_type or "",
             "allowance": centavos(f.monthly_allowance), "note": f.allowance_note or "", "status": words(f.status), "card": words(f.card_state)} for f in cards]
    return (
        [col("holder", "Holder"), col("company", "Company"), col("plate", "Plate"), col("fuel", "Fuel"), col("allowance", "Monthly allowance", "money"), col("note", "Allowance note"), col("status", "Status"), col("card", "Card")],
        rows,
        [fig("Cards", len(rows)), fig("Active", sum(1 for f in cards if f.card_state == "active"), tone="good"), fig("Monthly allowances", sum(r["allowance"] or 0 for r in rows), "money")],
        None,
    )


def travel(c: Ctx):
    trips = [t for t in c.db.scalars(select(TravelSponsorship)) if c.within(t.requested_on or t.created_at)]
    trips.sort(key=lambda t: c.day(t.requested_on or t.created_at))
    rows = [{"requested": c.day(t.requested_on or t.created_at).isoformat(), "rep": t.rep_name, "doctor": t.doctor_name, "kind": words(t.kind), "dates": t.travel_dates or "",
             "booking": t.hotel_or_flight or "", "status": words(t.status), "next": t.next_step or ""} for t in trips]
    waiting = sum(1 for t in trips if t.status in ("for_approval", "for_processing"))
    return (
        [col("requested", "Requested", "date"), col("rep", "Requested by"), col("doctor", "Doctor"), col("kind", "Type"), col("dates", "Travel dates"), col("booking", "Hotel or flight"), col("status", "Status"), col("next", "Next step")],
        rows,
        [fig("Requests", len(rows)), fig("Booked", sum(1 for t in trips if t.status == "booked"), tone="good"), fig("Awaiting approval or processing", waiting, tone="warn" if waiting else None)],
        None,
    )


def travel_by_rep(c: Ctx):
    by: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t in c.db.scalars(select(TravelSponsorship)):
        if c.within(t.requested_on or t.created_at) and t.status != "cancelled":
            by[t.rep_name][t.kind] += 1
    rows = [{"rep": rep, "hotel": k["hotel"], "flight": k["flight"], "total": sum(k.values())} for rep, k in sorted(by.items(), key=lambda x: -sum(x[1].values()))]
    return ([col("rep", "Requested by"), col("hotel", "Hotel", "number"), col("flight", "Flight", "number"), col("total", "Total", "number")], rows,
            [fig("Requests", sum(r["total"] for r in rows)), fig("People", len(rows))], bar("rep", "hotel", "flight") if rows else None)


def devices(c: Ctx):
    found = [d for d in c.db.scalars(select(DeviceIssue)) if c.within(d.issued_on or d.created_at)]
    found.sort(key=lambda d: c.day(d.issued_on or d.created_at))
    rows = [{"issued": c.day(d.issued_on or d.created_at).isoformat(), "to": d.issued_to, "laptop": d.laptop or "", "phone": d.phone or "", "sim": d.sim or "", "condition": words(d.condition), "signed": d.signed_by or ""} for d in found]
    return (
        [col("issued", "Issued", "date"), col("to", "Issued to"), col("laptop", "Laptop"), col("phone", "Phone"), col("sim", "SIM"), col("condition", "Condition"), col("signed", "Signed by")],
        rows,
        [fig("Issued", len(rows)), fig("Laptops", sum(1 for d in found if d.laptop)), fig("Phones", sum(1 for d in found if d.phone))],
        None,
    )


# --- Service requests -------------------------------------------------------------------------------


def tickets_by_category(c: Ctx):
    by: dict[str, dict] = defaultdict(lambda: {"opened": 0, "resolved": 0, "open": 0, "hours": []})
    for t in c.db.scalars(select(Ticket)):
        if not c.within(t.created_at):
            continue
        k = by[words(t.category)]
        k["opened"] += 1
        if t.status in CLOSED_TICKETS:
            k["resolved"] += 1
            if t.resolved_at:
                k["hours"].append((aware(t.resolved_at) - aware(t.created_at)).total_seconds() / 3600)
        else:
            k["open"] += 1
    rows = [{"category": cat, "opened": v["opened"], "resolved": v["resolved"], "open": v["open"], "hours": round(sum(v["hours"]) / len(v["hours"]), 1) if v["hours"] else None} for cat, v in sorted(by.items())]
    still = sum(r["open"] for r in rows)
    return (
        [col("category", "Category"), col("opened", "Opened", "number"), col("resolved", "Resolved", "number"), col("open", "Still open", "number"), col("hours", "Average hours to resolve", "number")],
        rows,
        [fig("Opened", sum(r["opened"] for r in rows)), fig("Resolved", sum(r["resolved"] for r in rows), tone="good"), fig("Still open", still, tone="warn" if still else None)],
        bar("category", "resolved", "open"),
    )


def tickets_overdue(c: Ctx):
    found = [t for t in c.db.scalars(select(Ticket).where(Ticket.status.not_in(CLOSED_TICKETS), Ticket.sla_due_date.is_not(None))) if c.day(t.sla_due_date) < c.today]
    found.sort(key=lambda t: c.day(t.sla_due_date))
    rows = [{"number": t.ticket_number, "title": t.title, "category": words(t.category), "priority": words(t.priority), "requester": t.requester_name, "assigned": t.assigned_to or "",
             "due": c.day(t.sla_due_date).isoformat(), "late": (c.today - c.day(t.sla_due_date)).days, "status": words(t.status)} for t in found]
    return (
        [col("number", "Request"), col("title", "Title"), col("category", "Category"), col("priority", "Priority"), col("requester", "Requested by"), col("assigned", "Assigned to"),
         col("due", "Due", "date"), col("late", "Days late", "number"), col("status", "Status")],
        rows,
        [fig("Past due", len(rows), tone="bad" if rows else "good")],
        None,
    )


def tickets_by_assignee(c: Ctx):
    by: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for t in c.db.scalars(select(Ticket)):
        if c.within(t.created_at):
            k = by[t.assigned_to or "(not assigned)"]
            k[0] += 1
            k[1 if t.status in CLOSED_TICKETS else 2] += 1
    rows = [{"assignee": n, "opened": v[0], "resolved": v[1], "open": v[2]} for n, v in sorted(by.items())]
    return ([col("assignee", "Assigned to"), col("opened", "Requests", "number"), col("resolved", "Resolved", "number"), col("open", "Still open", "number")], rows,
            [fig("Requests", sum(r["opened"] for r in rows))], bar("assignee", "resolved", "open") if rows else None)


# --- Marketing --------------------------------------------------------------------------------------


def materials_stock(c: Ctx):
    mats = list(c.db.scalars(select(PromoMaterial).order_by(PromoMaterial.title)))
    produced: dict[str, list] = defaultdict(lambda: [0, 0])
    for p in c.db.scalars(select(PromoProduction).where(PromoProduction.status != "cancelled")):
        produced[p.material_id][0] += p.quantity
        produced[p.material_id][1] += centavos(p.cost) or 0
    given: dict[str, int] = defaultdict(int)
    for d in c.db.scalars(select(PromoDistribution).where(PromoDistribution.status == "distributed")):
        given[d.material_id] += d.quantity
    rows = [{"title": m.title, "kind": m.kind, "product": m.product or "", "status": words(m.status), "produced": produced[m.id][0], "given": given[m.id], "stock": m.stock,
             "cost": produced[m.id][1], "budget": centavos(m.budget)} for m in mats]
    return (
        [col("title", "Material"), col("kind", "Kind"), col("product", "Product"), col("status", "Status"), col("produced", "Produced", "number"), col("given", "Given out", "number"),
         col("stock", "In stock", "number"), col("cost", "Production cost", "money"), col("budget", "Budget", "money")],
        rows,
        [fig("Materials", len(rows)), fig("In stock", sum(r["stock"] for r in rows)), fig("Production cost", sum(r["cost"] for r in rows), "money")],
        None,
    )


def distributions(c: Ctx):
    titles = {m.id: m.title for m in c.db.scalars(select(PromoMaterial))}
    found = [d for d in c.db.scalars(select(PromoDistribution)) if c.within(d.distributed_on or d.created_at)]
    found.sort(key=lambda d: c.day(d.distributed_on or d.created_at))
    rows = [{"date": c.day(d.distributed_on or d.created_at).isoformat(), "material": titles.get(d.material_id, ""), "team": d.team_name, "recipient": d.recipient_name or "",
             "quantity": d.quantity, "status": words(d.status), "manager": d.manager_name or ""} for d in found]
    waiting = sum(1 for d in found if d.status == "for_approval")
    return (
        [col("date", "Date", "date"), col("material", "Material"), col("team", "Team"), col("recipient", "Recipient"), col("quantity", "Quantity", "number"), col("status", "Status"), col("manager", "Approved by")],
        rows,
        [fig("Requests", len(rows)), fig("Units given out", sum(d.quantity for d in found if d.status == "distributed"), tone="good"), fig("Awaiting approval", waiting, tone="warn" if waiting else None)],
        None,
    )


RENEWALS = ("permits.view", "immigration.view", "documents.view", "properties.view")


def registry(access: Access) -> tuple[Report, ...]:
    return (
        Report("renewals-due", "Renewals due", "Compliance", "Permits, expatriates' papers, documents and leases that fall due in the period, soonest first.", renewals_due(access), RENEWALS, ahead=True),
        Report("expired-records", "Expired and not renewed", "Compliance", "Everything past its expiry date that hasn't been renewed or closed.", expired_records(access), RENEWALS, dated=False),
        Report("permits-by-agency", "Permits by agency", "Compliance", "Each agency's permits, how many are active, in renewal or expired, and what renewing costs.", permits_by_agency, ("permits.view",), dated=False, fixed=True),
        Report("leases", "Lease schedule", "Compliance", "Every lease in force: when it ends, when notice must be given, and the rent.", leases, ("properties.view",), dated=False, fixed=True),
        Report("vehicle-dues", "Vehicle renewals and maintenance", "Fleet and travel", "Registration, insurance and maintenance falling due in the period, with anything overdue.", vehicle_dues, ("vehicles.view",), ahead=True),
        Report("fuel-cards", "Fuel cards", "Fleet and travel", "Every fuel card, who holds it, and the monthly allowance.", fuel_cards, ("vehicles.view",), dated=False),
        Report("travel", "Hotel and flight requests", "Fleet and travel", "Sponsorships requested in the period and where each stands.", travel, ("travel.view",)),
        Report("travel-by-rep", "Travel requests by requester", "Fleet and travel", "Who asked for hotels and flights in the period.", travel_by_rep, ("travel.view",)),
        Report("devices", "Devices issued", "Fleet and travel", "Laptops, phones and SIMs issued in the period.", devices, ("devices.view",)),
        Report("requests-by-category", "Office requests by category", "Service requests", "Requests opened in the period, how many were resolved, and how long it took.", tickets_by_category, ("tickets.view",)),
        Report("requests-by-assignee", "Office requests by assignee", "Service requests", "Requests opened in the period, by who handles them.", tickets_by_assignee, ("tickets.view",)),
        Report("requests-overdue", "Overdue office requests", "Service requests", "Open requests past their due date, most overdue first.", tickets_overdue, ("tickets.view",), dated=False),
        Report("materials-stock", "Promotional materials stock", "Marketing", "Each material: produced, given out, in stock, and what it cost.", materials_stock, ("materials.view",), dated=False),
        Report("distributions", "Material distributions", "Marketing", "Materials requested for teams in the period, and what was given out.", distributions, ("materials.view",)),
    )


def allowed(r: Report, access: Access) -> bool:
    return any(access.can(p) for p in r.needs)


@router.get("")
def list_reports(access: CurrentAccess) -> list[dict]:
    return [{"key": r.key, "title": r.title, "group": r.group, "about": r.about, "dated": r.dated, "fixed": r.fixed} for r in registry(access) if allowed(r, access)]


def read_report(access: Access, db: Session, settings, key: str, start: date | None, end: date | None) -> dict:
    r = next((r for r in registry(access) if r.key == key), None)
    if r is None or not allowed(r, access):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such report.")
    zone = ZoneInfo(settings.org_timezone)
    today = datetime.now(zone).date()
    if r.ahead:
        start = start or today
        end = end or start + timedelta(days=90)
    else:
        end = end or today
        start = start or end.replace(day=1)
    if start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The period starts after it ends.")
    columns, rows, summary, chart = r.build(Ctx(db=db, zone=zone, today=today, first=start, last=end))
    return {"key": r.key, "title": r.title, "group": r.group, "about": r.about, "dated": r.dated, "fixed": r.fixed, "from": start.isoformat(), "to": end.isoformat(),
            "filters": [], "columns": columns, "rows": rows, "summary": summary, "chart": chart}


def _route(key: str):
    def one(access: CurrentAccess, db: DB, settings: SettingsDep, start: date | None = Query(None, alias="from"), end: date | None = Query(None, alias="to")) -> dict:
        return read_report(access, db, settings, key, start, end)

    return one


# One fixed path per report, so they're matched before the Excel exports' /admin/reports/{kind}
# (app/routers/sheets.py); main.py includes this router first.
for _key in [r.key for r in registry(Access(user=None, permissions=frozenset()))]:  # type: ignore[arg-type]
    router.add_api_route(f"/{_key}", _route(_key), methods=["GET"], name=f"report {_key}")
