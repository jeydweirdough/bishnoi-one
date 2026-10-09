"""Executive Admin's endpoints: Cockpit dashboard, permits & registrations (BOC/SEC/BIR/LGU/FDA),

immigration & visas (ACR/AEP), corporate documents, properties & leases, office concerns & tickets,
and countdown notifications.
"""

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from pydantic.alias_generators import to_camel
from sqlalchemy import desc, func, or_, select

from app.access import (
    access_of,
    allowed,
    keep_an_administrator,
    permissions_of,
    permitted,
)
from app.api import Api, changed, check_email, field_error, iso
from app.audit import audit
from app.config import Settings
from app.deps import DB, CurrentUser, SettingsDep
from app.executive import (
    calculate_days_remaining,
    safe_tz,
    sync_notifications,
    today_in_org,
    urgency_tier,
)
from app.models import (
    AuditEntry,
    ComplianceRecord,
    CorporateDocument,
    ImmigrationRecord,
    Notification,
    PropertyRecord,
    Role,
    RolePermission,
    SignInSession,
    Ticket,
    TicketUpdate,
    User,
    new_id,
    utcnow,
)
from app.permissions import ALL_PERMISSIONS, catalogue_out
from app.security import check_password_rules, hash_password

router = APIRouter(prefix="/admin", tags=["admin"])



# --- Serializers -------------------------------------------------------------


def serialize_permit(p: ComplianceRecord, settings: Settings) -> dict[str, Any]:
    days = calculate_days_remaining(p.expiration_date, settings)
    return {
        "id": p.id,
        "title": p.title,
        "category": p.category,
        "agency": p.agency,
        "referenceNumber": p.reference_number,
        "issuanceDate": p.issuance_date.isoformat() if p.issuance_date else None,
        "expirationDate": p.expiration_date.isoformat(),
        "renewalWindowDays": p.renewal_window_days,
        "status": p.status,
        "responsiblePerson": p.responsible_person,
        "estimatedCost": p.estimated_cost,
        "notes": p.notes,
        "daysRemaining": days,
        "urgencyTier": urgency_tier(days),
        "createdAt": p.created_at.isoformat(),
        "updatedAt": p.updated_at.isoformat(),
    }


def serialize_immigration(im: ImmigrationRecord, settings: Settings) -> dict[str, Any]:
    days = calculate_days_remaining(im.expiration_date, settings)
    return {
        "id": im.id,
        "individualName": im.individual_name,
        "designation": im.designation,
        "nationality": im.nationality,
        "documentType": im.document_type,
        "documentNumber": im.document_number,
        "issuanceDate": im.issuance_date.isoformat() if im.issuance_date else None,
        "expirationDate": im.expiration_date.isoformat(),
        "renewalLeadDays": im.renewal_lead_days,
        "sponsoringEntity": im.sponsoring_entity,
        "status": im.status,
        "assignedAssistant": im.assigned_assistant,
        "notes": im.notes,
        "daysRemaining": days,
        "urgencyTier": urgency_tier(days),
        "createdAt": im.created_at.isoformat(),
        "updatedAt": im.updated_at.isoformat(),
    }


def serialize_document(d: CorporateDocument, settings: Settings) -> dict[str, Any]:
    days = calculate_days_remaining(d.expiration_date, settings)
    return {
        "id": d.id,
        "title": d.title,
        "category": d.category,
        "counterparty": d.counterparty,
        "referenceNumber": d.reference_number,
        "effectiveDate": d.effective_date.isoformat() if d.effective_date else None,
        "expirationDate": d.expiration_date.isoformat() if d.expiration_date else None,
        "autoRenews": d.auto_renews,
        "noticePeriodDays": d.notice_period_days,
        "custodian": d.custodian,
        "status": d.status,
        "annualValue": d.annual_value,
        "notes": d.notes,
        "daysRemaining": days,
        "urgencyTier": urgency_tier(days),
        "createdAt": d.created_at.isoformat(),
        "updatedAt": d.updated_at.isoformat(),
    }


def serialize_property(pr: PropertyRecord, settings: Settings) -> dict[str, Any]:
    days = calculate_days_remaining(pr.lease_end, settings)
    return {
        "id": pr.id,
        "name": pr.name,
        "propertyType": pr.property_type,
        "address": pr.address,
        "lessorName": pr.lessor_name,
        "lessorContact": pr.lessor_contact,
        "leaseStart": pr.lease_start.isoformat() if pr.lease_start else None,
        "leaseEnd": pr.lease_end.isoformat(),
        "noticeDeadlineDays": pr.notice_deadline_days,
        "monthlyRent": pr.monthly_rent,
        "escalationRatePct": pr.escalation_rate_pct,
        "securityDeposit": pr.security_deposit,
        "utilitiesInfo": pr.utilities_info,
        "status": pr.status,
        "assignedManager": pr.assigned_manager,
        "notes": pr.notes,
        "daysRemaining": days,
        "urgencyTier": urgency_tier(days),
        "createdAt": pr.created_at.isoformat(),
        "updatedAt": pr.updated_at.isoformat(),
    }


def serialize_ticket(tk: Ticket, settings: Settings, updates: list[TicketUpdate] | None = None) -> dict[str, Any]:
    days = calculate_days_remaining(tk.sla_due_date, settings)
    res = {
        "id": tk.id,
        "ticketNumber": tk.ticket_number,
        "title": tk.title,
        "category": tk.category,
        "priority": tk.priority,
        "status": tk.status,
        "requesterName": tk.requester_name,
        "requesterEmail": tk.requester_email,
        "executiveSponsor": tk.executive_sponsor,
        "assignedTo": tk.assigned_to,
        "slaDueDate": tk.sla_due_date.isoformat() if tk.sla_due_date else None,
        "description": tk.description,
        "resolutionNotes": tk.resolution_notes,
        "daysRemaining": days,
        "urgencyTier": urgency_tier(days),
        "createdAt": tk.created_at.isoformat(),
        "resolvedAt": tk.resolved_at.isoformat() if tk.resolved_at else None,
        "updatedAt": tk.updated_at.isoformat(),
    }
    if updates is not None:
        res["updates"] = [
            {
                "id": u.id,
                "authorName": u.author_name,
                "authorEmail": u.author_email,
                "updateType": u.update_type,
                "content": u.content,
                "createdAt": u.created_at.isoformat(),
            }
            for u in updates
        ]
    return res


def serialize_notification(n: Notification) -> dict[str, Any]:
    return {
        "id": n.id,
        "entityType": n.entity_type,
        "entityId": n.entity_id,
        "severity": n.severity,
        "title": n.title,
        "message": n.message,
        "daysRemaining": n.days_remaining,
        "dueDate": n.due_date.isoformat() if n.due_date else None,
        "isRead": n.is_read,
        "isAcknowledged": n.is_acknowledged,
        "isResolved": n.is_resolved,
        "createdAt": n.created_at.isoformat(),
        "updatedAt": n.updated_at.isoformat(),
    }


# --- Executive Cockpit Dashboard ---------------------------------------------


@router.get("/dashboard")
def executive_dashboard(user: permitted("dashboard.view"), db: DB, settings: SettingsDep) -> dict[str, Any]:
    """Executive Cockpit summary figures, compliance score, countdown highlights,

    and urgent actions for executive admins & assistants.
    """
    sync_notifications(db, settings)
    today = today_in_org(settings)

    # 1. Permits stats
    all_permits = db.scalars(select(ComplianceRecord)).all()
    permits_total = len(all_permits)
    permits_overdue = 0
    permits_urgent = 0
    permits_approaching = 0
    for p in all_permits:
        days = (p.expiration_date.date() - today).days
        if days < 0:
            permits_overdue += 1
        elif days <= 15:
            permits_urgent += 1
        elif days <= 30:
            permits_approaching += 1

    # 2. Immigration stats
    all_immig = db.scalars(select(ImmigrationRecord)).all()
    immig_total = len(all_immig)
    immig_expiring = sum(1 for im in all_immig if 0 <= (im.expiration_date.date() - today).days <= 60)
    immig_overdue = sum(1 for im in all_immig if (im.expiration_date.date() - today).days < 0)

    # 3. Documents stats
    all_docs = db.scalars(select(CorporateDocument)).all()
    docs_total = len(all_docs)
    insurances_total = sum(1 for d in all_docs if d.category == "insurance")

    # 4. Properties stats
    all_props = db.scalars(select(PropertyRecord)).all()
    props_total = len(all_props)
    leases_expiring = sum(1 for pr in all_props if 0 <= (pr.lease_end.date() - today).days <= 90)

    # 5. Tickets stats
    all_tickets = db.scalars(select(Ticket)).all()
    tickets_open = sum(1 for t in all_tickets if t.status in ["open", "in_progress", "pending_vendor"])
    tickets_urgent = sum(
        1 for t in all_tickets if t.status in ["open", "in_progress"] and t.priority in ["urgent", "high"]
    )

    # 6. Notifications stats
    active_notifs = db.scalars(
        select(Notification).where(Notification.is_resolved.is_(False)).order_by(desc(Notification.severity))
    ).all()
    notifs_unread = sum(1 for n in active_notifs if not n.is_read)
    notifs_critical = sum(1 for n in active_notifs if n.severity in ["critical", "urgent"])

    # 7. Unified Countdown Highlights (Top 8 items requiring executive attention)
    highlights = []

    for p in all_permits:
        days = (p.expiration_date.date() - today).days
        if days <= 60:
            highlights.append(
                {
                    "entityType": "permit",
                    "entityId": p.id,
                    "title": p.title,
                    "subtitle": p.agency,
                    "reference": p.reference_number,
                    "dueDate": p.expiration_date.isoformat(),
                    "daysRemaining": days,
                    "urgencyTier": urgency_tier(days),
                    "actionPath": "/permits",
                }
            )

    for im in all_immig:
        days = (im.expiration_date.date() - today).days
        if days <= 60:
            doc_label = {
                "visa": "Visa",
                "acr_card": "ACR I-Card",
                "aep_permit": "DOLE AEP",
                "passport": "Passport",
            }.get(im.document_type, im.document_type.upper())
            highlights.append(
                {
                    "entityType": "immigration",
                    "entityId": im.id,
                    "title": f"{im.individual_name} ({doc_label})",
                    "subtitle": im.designation,
                    "reference": im.document_number,
                    "dueDate": im.expiration_date.isoformat(),
                    "daysRemaining": days,
                    "urgencyTier": urgency_tier(days),
                    "actionPath": "/immigration",
                }
            )

    for pr in all_props:
        days = (pr.lease_end.date() - today).days
        if days <= 90:
            highlights.append(
                {
                    "entityType": "property",
                    "entityId": pr.id,
                    "title": pr.name,
                    "subtitle": f"Lease with {pr.lessor_name}",
                    "reference": f"{pr.notice_deadline_days}d Notice",
                    "dueDate": pr.lease_end.isoformat(),
                    "daysRemaining": days,
                    "urgencyTier": urgency_tier(days),
                    "actionPath": "/properties",
                }
            )

    for d in all_docs:
        if d.expiration_date:
            days = (d.expiration_date.date() - today).days
            if days <= 60:
                highlights.append(
                    {
                        "entityType": "document",
                        "entityId": d.id,
                        "title": d.title,
                        "subtitle": d.counterparty,
                        "reference": d.reference_number or "Contract",
                        "dueDate": d.expiration_date.isoformat(),
                        "daysRemaining": days,
                        "urgencyTier": urgency_tier(days),
                        "actionPath": "/documents",
                    }
                )

    for tk in all_tickets:
        if tk.status in ["open", "in_progress"] and tk.sla_due_date:
            days = (tk.sla_due_date.date() - today).days
            if days <= 3:
                highlights.append(
                    {
                        "entityType": "ticket",
                        "entityId": tk.id,
                        "title": f"{tk.ticket_number}: {tk.title}",
                        "subtitle": f"{tk.priority.capitalize()} priority · requested by {tk.requester_name}",
                        "reference": tk.category,
                        "dueDate": tk.sla_due_date.isoformat(),
                        "daysRemaining": days,
                        "urgencyTier": urgency_tier(days),
                        "actionPath": "/tickets",
                    }
                )

    # Fleet and travel: a car's dates within 60 days, a trip within 14 that isn't approved or booked.
    from app.routers.operations import summary as fleet_summary, vehicle_dues

    fleet = fleet_summary(db, settings)
    for v in fleet["vehicles"]:
        car = " ".join(x for x in (v.name, v.plate) if x)
        for due in vehicle_dues(v, today):
            if due["daysRemaining"] <= 60:
                highlights.append({
                    "entityType": f"vehicle_{due['what']}", "entityId": v.id, "title": car, "subtitle": due["label"],
                    "reference": v.owner_name or "Company vehicle", "dueDate": due["date"],
                    "daysRemaining": due["daysRemaining"], "urgencyTier": due["urgencyTier"], "actionPath": f"/vehicles/{v.id}",
                })
    for t in fleet["trips"]:
        if t.starts_on and t.status in ("for_approval", "for_processing"):
            days = (t.starts_on - today).days
            if days <= 14:
                highlights.append({
                    "entityType": "travel", "entityId": t.id, "title": t.doctor_name,
                    "subtitle": f"{'Hotel' if t.kind == 'hotel' else 'Flight'} not settled · asked by {t.rep_name}",
                    "reference": t.travel_dates or "", "dueDate": t.starts_on.isoformat(),
                    "daysRemaining": days, "urgencyTier": urgency_tier(days), "actionPath": f"/travel/{t.id}",
                })

    # Sort countdown highlights by urgency (most overdue first, then fewest days remaining)
    highlights.sort(key=lambda x: x["daysRemaining"])

    # 8. Health per area: current, due soon (inside the area's own renewal
    # window) or overdue, for the overview's status bars.
    dated = {
        "permits": ("Permits", "/permits", 30, [p.expiration_date.date() for p in all_permits]),
        "expatriates": ("Expatriates", "/immigration", 60, [im.expiration_date.date() for im in all_immig]),
        "documents": ("Documents", "/documents", 60, [d.expiration_date.date() for d in all_docs if d.expiration_date]),
        "properties": ("Leases", "/properties", 90, [pr.lease_end.date() for pr in all_props]),
        "vehicles": ("Vehicles", "/vehicles", 30, [d for v in fleet["vehicles"] for d in (v.registration_due, v.insurance_due, v.pms_due) if d]),
    }
    health = []
    for key, (label, href, window, dates) in dated.items():
        overdue = sum(1 for due in dates if due < today)
        due_soon = sum(1 for due in dates if 0 <= (due - today).days <= window)
        health.append({
            "key": key, "label": label, "href": href, "windowDays": window,
            "total": len(dates), "current": len(dates) - overdue - due_soon, "dueSoon": due_soon, "overdue": overdue,
        })
    open_tickets = [t for t in all_tickets if t.status in ["open", "in_progress", "pending_vendor"]]
    late = sum(1 for t in open_tickets if t.sla_due_date and t.sla_due_date.date() < today)

    # 9. Renewals falling due per month: anything overdue, then the next six months.
    months = []
    first = today.replace(day=1)
    for i in range(6):
        y, m = divmod(first.month - 1 + i, 12)
        months.append(f"{first.year + y}-{m + 1:02d}")
    by_month = {"overdue": dict.fromkeys(dated, 0), **{mo: dict.fromkeys(dated, 0) for mo in months}}
    for key, (_, _, _, dates) in dated.items():
        for due in dates:
            bucket = "overdue" if due < today else f"{due.year}-{due.month:02d}"
            if bucket in by_month:
                by_month[bucket][key] += 1

    return {
        "health": health,
        "requests": {"open": len(open_tickets), "late": late, "onTime": len(open_tickets) - late},
        "renewalsByMonth": [{"month": mo, **counts} for mo, counts in by_month.items()],
        "stats": {
            "permits": {
                "total": permits_total,
                "overdue": permits_overdue,
                "urgent": permits_urgent,
                "approaching": permits_approaching,
            },
            "immigration": {
                "total": immig_total,
                "expiringSoon": immig_expiring,
                "overdue": immig_overdue,
            },
            "documents": {
                "total": docs_total,
                "insurancePolicies": insurances_total,
            },
            "properties": {
                "total": props_total,
                "leasesExpiring": leases_expiring,
            },
            "tickets": {
                "totalOpen": tickets_open,
                "urgent": tickets_urgent,
            },
            **fleet["stats"],
            "notifications": {
                "totalActive": len(active_notifs),
                "unread": notifs_unread,
                "critical": notifs_critical,
            },
        },
        "countdownHighlights": highlights,
    }


# --- Registrations & Permits (BOC, SEC, BIR, LGU, FDA) -----------------------


class PermitInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=40)  # boc, lgu, sec, bir, fda, sanitary_fire, other
    agency: str = Field(min_length=2, max_length=100)
    referenceNumber: str = Field(min_length=1, max_length=80)
    issuanceDate: str | None = None
    expirationDate: str
    renewalWindowDays: int = 60
    status: str = "active"
    responsiblePerson: str | None = None
    estimatedCost: float | None = None
    notes: str | None = None


def parse_iso_datetime(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    cleaned = dt_str.replace("Z", "+00:00")
    if len(cleaned) == 10:  # YYYY-MM-DD
        cleaned += "T00:00:00+00:00"
    return datetime.fromisoformat(cleaned)


@router.get("/permits")
def list_permits(
    user: permitted("permits.view"),
    db: DB,
    settings: SettingsDep,
    category: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
) -> list[dict[str, Any]]:
    query = select(ComplianceRecord)
    if category:
        query = query.where(ComplianceRecord.category == category)
    if status_filter:
        query = query.where(ComplianceRecord.status == status_filter)
    query = query.order_by(ComplianceRecord.expiration_date.asc())
    records = db.scalars(query).all()
    return [serialize_permit(r, settings) for r in records]


@router.post("/permits", status_code=status.HTTP_201_CREATED)
def create_permit(user: permitted("permits.create"), payload: PermitInput, db: DB, settings: SettingsDep) -> dict[str, Any]:
    exp_dt = parse_iso_datetime(payload.expirationDate)
    if not exp_dt:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Valid expiration date is required.")
    rec = ComplianceRecord(
        id=new_id(),
        title=payload.title.strip(),
        category=payload.category.strip(),
        agency=payload.agency.strip(),
        reference_number=payload.referenceNumber.strip(),
        issuance_date=parse_iso_datetime(payload.issuanceDate),
        expiration_date=exp_dt,
        renewal_window_days=payload.renewalWindowDays,
        status=payload.status,
        responsible_person=payload.responsiblePerson.strip() if payload.responsiblePerson else None,
        estimated_cost=payload.estimatedCost,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    sync_notifications(db, settings)
    return serialize_permit(rec, settings)


@router.patch("/permits/{permit_id}")
def update_permit(permit_id: str, user: permitted("permits.edit"), payload: PermitInput, db: DB, settings: SettingsDep) -> dict[str, Any]:
    rec = db.get(ComplianceRecord, permit_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permit record not found.")
    exp_dt = parse_iso_datetime(payload.expirationDate)
    if not exp_dt:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Valid expiration date is required.")
    rec.title = payload.title.strip()
    rec.category = payload.category.strip()
    rec.agency = payload.agency.strip()
    rec.reference_number = payload.referenceNumber.strip()
    rec.issuance_date = parse_iso_datetime(payload.issuanceDate)
    rec.expiration_date = exp_dt
    rec.renewal_window_days = payload.renewalWindowDays
    rec.status = payload.status
    rec.responsible_person = payload.responsiblePerson.strip() if payload.responsiblePerson else None
    rec.estimated_cost = payload.estimatedCost
    rec.notes = payload.notes.strip() if payload.notes else None
    rec.updated_at = utcnow()
    db.commit()
    db.refresh(rec)
    sync_notifications(db, settings)
    return serialize_permit(rec, settings)


@router.delete("/permits/{permit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_permit(permit_id: str, user: permitted("permits.delete"), db: DB, settings: SettingsDep):
    rec = db.get(ComplianceRecord, permit_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Permit record not found.")
    db.delete(rec)
    db.commit()
    return None


# --- Expatriate & Immigration Compliance (ACR, AEP, Visas, Passports) --------


class ImmigrationInput(BaseModel):
    individualName: str = Field(min_length=2, max_length=120)
    designation: str = Field(min_length=2, max_length=120)
    nationality: str = Field(min_length=2, max_length=60)
    documentType: str = Field(min_length=2, max_length=40)  # visa, acr_card, aep_permit, passport, exec_id
    documentNumber: str = Field(min_length=1, max_length=80)
    issuanceDate: str | None = None
    expirationDate: str
    renewalLeadDays: int = 60
    sponsoringEntity: str | None = None
    status: str = "valid"
    assignedAssistant: str | None = None
    notes: str | None = None


@router.get("/immigration")
def list_immigration(
    user: permitted("immigration.view"),
    db: DB,
    settings: SettingsDep,
    doc_type: str | None = Query(None, alias="documentType"),
) -> list[dict[str, Any]]:
    query = select(ImmigrationRecord)
    if doc_type:
        query = query.where(ImmigrationRecord.document_type == doc_type)
    query = query.order_by(ImmigrationRecord.expiration_date.asc())
    records = db.scalars(query).all()
    return [serialize_immigration(r, settings) for r in records]


@router.post("/immigration", status_code=status.HTTP_201_CREATED)
def create_immigration(user: permitted("immigration.create"), payload: ImmigrationInput, db: DB, settings: SettingsDep) -> dict[str, Any]:
    exp_dt = parse_iso_datetime(payload.expirationDate)
    if not exp_dt:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Valid expiration date is required.")
    rec = ImmigrationRecord(
        id=new_id(),
        individual_name=payload.individualName.strip(),
        designation=payload.designation.strip(),
        nationality=payload.nationality.strip(),
        document_type=payload.documentType.strip(),
        document_number=payload.documentNumber.strip(),
        issuance_date=parse_iso_datetime(payload.issuanceDate),
        expiration_date=exp_dt,
        renewal_lead_days=payload.renewalLeadDays,
        sponsoring_entity=payload.sponsoringEntity.strip() if payload.sponsoringEntity else None,
        status=payload.status,
        assigned_assistant=payload.assignedAssistant.strip() if payload.assignedAssistant else None,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    sync_notifications(db, settings)
    return serialize_immigration(rec, settings)


@router.patch("/immigration/{record_id}")
def update_immigration(
    record_id: str, user: permitted("immigration.edit"), payload: ImmigrationInput, db: DB, settings: SettingsDep
) -> dict[str, Any]:
    rec = db.get(ImmigrationRecord, record_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Immigration record not found.")
    exp_dt = parse_iso_datetime(payload.expirationDate)
    if not exp_dt:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Valid expiration date is required.")
    rec.individual_name = payload.individualName.strip()
    rec.designation = payload.designation.strip()
    rec.nationality = payload.nationality.strip()
    rec.document_type = payload.documentType.strip()
    rec.document_number = payload.documentNumber.strip()
    rec.issuance_date = parse_iso_datetime(payload.issuanceDate)
    rec.expiration_date = exp_dt
    rec.renewal_lead_days = payload.renewalLeadDays
    rec.sponsoring_entity = payload.sponsoringEntity.strip() if payload.sponsoringEntity else None
    rec.status = payload.status
    rec.assigned_assistant = payload.assignedAssistant.strip() if payload.assignedAssistant else None
    rec.notes = payload.notes.strip() if payload.notes else None
    rec.updated_at = utcnow()
    db.commit()
    db.refresh(rec)
    sync_notifications(db, settings)
    return serialize_immigration(rec, settings)


@router.delete("/immigration/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_immigration(record_id: str, user: permitted("immigration.delete"), db: DB, settings: SettingsDep):
    rec = db.get(ImmigrationRecord, record_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Immigration record not found.")
    db.delete(rec)
    db.commit()
    return None


# --- Corporate Documents & Contracts -----------------------------------------


class DocumentInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=40)
    counterparty: str = Field(min_length=2, max_length=140)
    referenceNumber: str | None = None
    effectiveDate: str | None = None
    expirationDate: str | None = None
    autoRenews: bool = False
    noticePeriodDays: int = 30
    custodian: str | None = None
    status: str = "active"
    annualValue: float | None = None
    notes: str | None = None


def missing_an_expiry():
    """In force with no expiry date and not renewing by itself, so no renewal alert can come."""
    return CorporateDocument.expiration_date.is_(None) & ~CorporateDocument.auto_renews & (CorporateDocument.status != "terminated")


@router.get("/documents")
def list_documents(
    user: permitted("documents.view"),
    db: DB,
    settings: SettingsDep,
    category: str | None = Query(None),
    missing: bool = Query(False, description="only documents in force with no expiry date"),
) -> list[dict[str, Any]]:
    query = select(CorporateDocument)
    if missing:
        query = query.where(missing_an_expiry())
    if category:
        query = query.where(CorporateDocument.category == category)
    query = query.order_by(CorporateDocument.expiration_date.asc())
    records = db.scalars(query).all()
    return [serialize_document(r, settings) for r in records]


@router.post("/documents", status_code=status.HTTP_201_CREATED)
def create_document(user: permitted("documents.create"), payload: DocumentInput, db: DB, settings: SettingsDep) -> dict[str, Any]:
    rec = CorporateDocument(
        id=new_id(),
        title=payload.title.strip(),
        category=payload.category.strip(),
        counterparty=payload.counterparty.strip(),
        reference_number=payload.referenceNumber.strip() if payload.referenceNumber else None,
        effective_date=parse_iso_datetime(payload.effectiveDate),
        expiration_date=parse_iso_datetime(payload.expirationDate),
        auto_renews=payload.autoRenews,
        notice_period_days=payload.noticePeriodDays,
        custodian=payload.custodian.strip() if payload.custodian else None,
        status=payload.status,
        annual_value=payload.annualValue,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    sync_notifications(db, settings)
    return serialize_document(rec, settings)


@router.patch("/documents/{doc_id}")
def update_document(doc_id: str, user: permitted("documents.edit"), payload: DocumentInput, db: DB, settings: SettingsDep) -> dict[str, Any]:
    rec = db.get(CorporateDocument, doc_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document record not found.")
    rec.title = payload.title.strip()
    rec.category = payload.category.strip()
    rec.counterparty = payload.counterparty.strip()
    rec.reference_number = payload.referenceNumber.strip() if payload.referenceNumber else None
    rec.effective_date = parse_iso_datetime(payload.effectiveDate)
    rec.expiration_date = parse_iso_datetime(payload.expirationDate)
    rec.auto_renews = payload.autoRenews
    rec.notice_period_days = payload.noticePeriodDays
    rec.custodian = payload.custodian.strip() if payload.custodian else None
    rec.status = payload.status
    rec.annual_value = payload.annualValue
    rec.notes = payload.notes.strip() if payload.notes else None
    rec.updated_at = utcnow()
    db.commit()
    db.refresh(rec)
    sync_notifications(db, settings)
    return serialize_document(rec, settings)


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: str, user: permitted("documents.delete"), db: DB, settings: SettingsDep):
    rec = db.get(CorporateDocument, doc_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document record not found.")
    db.delete(rec)
    db.commit()
    return None


# --- Real Estate & Properties (Offices, Warehouses, Utilities) ---------------


class PropertyInput(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    propertyType: str = Field(min_length=2, max_length=40)
    address: str = Field(min_length=2, max_length=250)
    lessorName: str = Field(min_length=2, max_length=140)
    lessorContact: str | None = None
    leaseStart: str | None = None
    leaseEnd: str
    noticeDeadlineDays: int = 90
    monthlyRent: float | None = None
    escalationRatePct: float | None = None
    securityDeposit: float | None = None
    utilitiesInfo: str | None = None
    status: str = "active"
    assignedManager: str | None = None
    notes: str | None = None


def missing_rent():
    """Leased and not ended, with no monthly rent written down."""
    return PropertyRecord.monthly_rent.is_(None) & (PropertyRecord.status != "terminated")


@router.get("/properties")
def list_properties(
    user: permitted("properties.view"),
    db: DB,
    settings: SettingsDep,
    property_type: str | None = Query(None, alias="propertyType"),
    missing: bool = Query(False, description="only properties not ended with no monthly rent"),
) -> list[dict[str, Any]]:
    query = select(PropertyRecord)
    if missing:
        query = query.where(missing_rent())
    if property_type:
        query = query.where(PropertyRecord.property_type == property_type)
    query = query.order_by(PropertyRecord.lease_end.asc())
    records = db.scalars(query).all()
    return [serialize_property(r, settings) for r in records]


@router.post("/properties", status_code=status.HTTP_201_CREATED)
def create_property(user: permitted("properties.create"), payload: PropertyInput, db: DB, settings: SettingsDep) -> dict[str, Any]:
    lease_end = parse_iso_datetime(payload.leaseEnd)
    if not lease_end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Valid lease end date is required.")
    rec = PropertyRecord(
        id=new_id(),
        name=payload.name.strip(),
        property_type=payload.propertyType.strip(),
        address=payload.address.strip(),
        lessor_name=payload.lessorName.strip(),
        lessor_contact=payload.lessorContact.strip() if payload.lessorContact else None,
        lease_start=parse_iso_datetime(payload.leaseStart),
        lease_end=lease_end,
        notice_deadline_days=payload.noticeDeadlineDays,
        monthly_rent=payload.monthlyRent,
        escalation_rate_pct=payload.escalationRatePct,
        security_deposit=payload.securityDeposit,
        utilities_info=payload.utilitiesInfo.strip() if payload.utilitiesInfo else None,
        status=payload.status,
        assigned_manager=payload.assignedManager.strip() if payload.assignedManager else None,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    sync_notifications(db, settings)
    return serialize_property(rec, settings)


@router.patch("/properties/{property_id}")
def update_property(
    property_id: str, user: permitted("properties.edit"), payload: PropertyInput, db: DB, settings: SettingsDep
) -> dict[str, Any]:
    rec = db.get(PropertyRecord, property_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property record not found.")
    lease_end = parse_iso_datetime(payload.leaseEnd)
    if not lease_end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Valid lease end date is required.")
    rec.name = payload.name.strip()
    rec.property_type = payload.propertyType.strip()
    rec.address = payload.address.strip()
    rec.lessor_name = payload.lessorName.strip()
    rec.lessor_contact = payload.lessorContact.strip() if payload.lessorContact else None
    rec.lease_start = parse_iso_datetime(payload.leaseStart)
    rec.lease_end = lease_end
    rec.notice_deadline_days = payload.noticeDeadlineDays
    rec.monthly_rent = payload.monthlyRent
    rec.escalation_rate_pct = payload.escalationRatePct
    rec.security_deposit = payload.securityDeposit
    rec.utilities_info = payload.utilitiesInfo.strip() if payload.utilitiesInfo else None
    rec.status = payload.status
    rec.assigned_manager = payload.assignedManager.strip() if payload.assignedManager else None
    rec.notes = payload.notes.strip() if payload.notes else None
    rec.updated_at = utcnow()
    db.commit()
    db.refresh(rec)
    sync_notifications(db, settings)
    return serialize_property(rec, settings)


@router.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(property_id: str, user: permitted("properties.delete"), db: DB, settings: SettingsDep):
    rec = db.get(PropertyRecord, property_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Property record not found.")
    db.delete(rec)
    db.commit()
    return None


# --- Office Concerns & Executive Service Desk (Tickets) ----------------------


class TicketInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=40)
    priority: str = "normal"  # urgent, high, normal, low
    status: str = "open"  # open, in_progress, pending_vendor, resolved, closed
    requesterName: str = Field(min_length=2, max_length=120)
    requesterEmail: str | None = None
    executiveSponsor: str | None = None
    assignedTo: str | None = None
    slaDueDate: str | None = None
    description: str = Field(min_length=2, max_length=1000)
    resolutionNotes: str | None = None


class TicketUpdateInput(BaseModel):
    authorName: str = Field(min_length=2, max_length=120)
    authorEmail: str | None = None
    updateType: str = "comment"  # comment, status_change, resolution
    content: str = Field(min_length=1, max_length=1000)
    newStatus: str | None = None


CLOSED = ("resolved", "closed")


def check_ticket_change(user: User, rec: Ticket, assigned_to: str | None, new_status: str) -> None:
    """Editing a request isn't all of it: handing it to someone else needs
    "assign", and closing it (or opening it again) needs "resolve"."""
    access = access_of(user)
    if (assigned_to or "").strip() != (rec.assigned_to or ""):
        access.require("tickets.assign")
    if (new_status in CLOSED) != (rec.status in CLOSED):
        access.require("tickets.resolve")


@router.get("/tickets")
def list_tickets(
    user: permitted("tickets.view"),
    db: DB,
    settings: SettingsDep,
    status_filter: str | None = Query(None, alias="status"),
    priority: str | None = Query(None),
) -> list[dict[str, Any]]:
    query = select(Ticket)
    if status_filter:
        query = query.where(Ticket.status == status_filter)
    if priority:
        query = query.where(Ticket.priority == priority)
    query = query.order_by(Ticket.created_at.desc())
    records = db.scalars(query).all()
    return [serialize_ticket(r, settings) for r in records]


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(user: permitted("tickets.create"), payload: TicketInput, db: DB, settings: SettingsDep) -> dict[str, Any]:
    # Generate sequential ticket number
    count = db.scalar(select(func.count(Ticket.id))) or 0
    now_year = datetime.now(safe_tz(settings.org_timezone)).year
    ticket_num = f"EX-{now_year}-{count + 1:04d}"

    rec = Ticket(
        id=new_id(),
        ticket_number=ticket_num,
        title=payload.title.strip(),
        category=payload.category.strip(),
        priority=payload.priority,
        status=payload.status,
        requester_name=payload.requesterName.strip(),
        requester_email=payload.requesterEmail.strip() if payload.requesterEmail else None,
        executive_sponsor=payload.executiveSponsor.strip() if payload.executiveSponsor else None,
        assigned_to=payload.assignedTo.strip() if payload.assignedTo else None,
        sla_due_date=parse_iso_datetime(payload.slaDueDate),
        description=payload.description.strip(),
        resolution_notes=payload.resolutionNotes.strip() if payload.resolutionNotes else None,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # Initial update log
    update = TicketUpdate(
        id=new_id(),
        ticket_id=rec.id,
        author_name=user.full_name,
        author_email=user.email,
        update_type="comment",
        content="Ticket logged and assigned to Executive Administration.",
    )
    db.add(update)
    db.commit()

    sync_notifications(db, settings)
    return serialize_ticket(rec, settings)


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, user: permitted("tickets.view"), db: DB, settings: SettingsDep) -> dict[str, Any]:
    rec = db.get(Ticket, ticket_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found.")
    updates = db.scalars(
        select(TicketUpdate).where(TicketUpdate.ticket_id == ticket_id).order_by(TicketUpdate.created_at.asc())
    ).all()
    return serialize_ticket(rec, settings, list(updates))


@router.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: str, user: permitted("tickets.edit"), payload: TicketInput, db: DB, settings: SettingsDep) -> dict[str, Any]:
    rec = db.get(Ticket, ticket_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found.")
    check_ticket_change(user, rec, payload.assignedTo, payload.status)
    rec.title = payload.title.strip()
    rec.category = payload.category.strip()
    rec.priority = payload.priority
    if rec.status != payload.status and payload.status in ["resolved", "closed"] and not rec.resolved_at:
        rec.resolved_at = utcnow()
    rec.status = payload.status
    rec.requester_name = payload.requesterName.strip()
    rec.requester_email = payload.requesterEmail.strip() if payload.requesterEmail else None
    rec.executive_sponsor = payload.executiveSponsor.strip() if payload.executiveSponsor else None
    rec.assigned_to = payload.assignedTo.strip() if payload.assignedTo else None
    rec.sla_due_date = parse_iso_datetime(payload.slaDueDate)
    rec.description = payload.description.strip()
    rec.resolution_notes = payload.resolutionNotes.strip() if payload.resolutionNotes else None
    rec.updated_at = utcnow()
    db.commit()
    db.refresh(rec)
    sync_notifications(db, settings)
    return serialize_ticket(rec, settings)


@router.post("/tickets/{ticket_id}/updates")
def add_ticket_update(
    ticket_id: str, user: permitted("tickets.edit"), payload: TicketUpdateInput, db: DB, settings: SettingsDep
) -> dict[str, Any]:
    rec = db.get(Ticket, ticket_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found.")
    check_ticket_change(user, rec, rec.assigned_to, payload.newStatus or rec.status)
    update = TicketUpdate(
        id=new_id(),
        ticket_id=ticket_id,
        author_name=payload.authorName.strip() or user.full_name,
        author_email=payload.authorEmail.strip() if payload.authorEmail else user.email,
        update_type=payload.updateType,
        content=payload.content.strip(),
    )
    db.add(update)
    if payload.newStatus and payload.newStatus != rec.status:
        rec.status = payload.newStatus
        if payload.newStatus in ["resolved", "closed"] and not rec.resolved_at:
            rec.resolved_at = utcnow()
        rec.updated_at = utcnow()
    db.commit()
    updates = db.scalars(
        select(TicketUpdate).where(TicketUpdate.ticket_id == ticket_id).order_by(TicketUpdate.created_at.asc())
    ).all()
    return serialize_ticket(rec, settings, list(updates))


@router.delete("/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(ticket_id: str, user: permitted("tickets.delete"), db: DB, settings: SettingsDep):
    rec = db.get(Ticket, ticket_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found.")
    db.delete(rec)
    db.commit()
    return None


# --- Proactive Renewal Alerts & Notifications Matrix -------------------------


@router.get("/notifications")
def list_notifications(
    user: permitted("notifications.view"),
    db: DB,
    settings: SettingsDep,
    unread_only: bool = Query(False, alias="unreadOnly"),
) -> list[dict[str, Any]]:
    sync_notifications(db, settings)
    query = select(Notification).where(Notification.is_resolved.is_(False))
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    query = query.order_by(desc(Notification.severity), Notification.days_remaining.asc())
    records = db.scalars(query).all()
    return [serialize_notification(r) for r in records]


@router.post("/notifications/sync")
def trigger_notification_sync(user: permitted("notifications.view"), db: DB, settings: SettingsDep) -> dict[str, Any]:
    count = sync_notifications(db, settings)
    return {"ok": True, "newOrUpdated": count}


@router.patch("/notifications/{notif_id}/acknowledge")
def acknowledge_notification(notif_id: str, user: permitted("notifications.acknowledge"), db: DB) -> dict[str, Any]:
    n = db.get(Notification, notif_id)
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found.")
    n.is_acknowledged = True
    n.is_read = True
    n.updated_at = utcnow()
    db.commit()
    return serialize_notification(n)


@router.patch("/notifications/{notif_id}/resolve")
def resolve_notification(notif_id: str, user: permitted("notifications.resolve"), db: DB) -> dict[str, Any]:
    n = db.get(Notification, notif_id)
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found.")
    n.is_resolved = True
    n.is_read = True
    n.updated_at = utcnow()
    db.commit()
    return serialize_notification(n)


# --- Administration (RBAC, Users, Roles, Activity Log) ----------------------

UsersPerm = allowed("admin.users")
RolesPerm = allowed("admin.roles")
AuditPerm = allowed("admin.audit")


def valid_password(value: str) -> str:
    problem = check_password_rules(value)
    if problem:
        raise ValueError(problem)
    return value


class UserIn(Api):
    email: str = Field(max_length=254)
    full_name: str = Field(min_length=1, max_length=120)
    role_id: str = Field(max_length=36)
    password: str = Field(max_length=256)

    _email = field_validator("email")(check_email)
    _password = field_validator("password")(valid_password)


class UserPatch(Api):
    email: str | None = Field(None, max_length=254)
    full_name: str | None = Field(None, min_length=1, max_length=120)
    role_id: str | None = Field(None, max_length=36)
    is_active: bool | None = None

    _email = field_validator("email")(check_email)


class PasswordIn(Api):
    password: str = Field(max_length=256)

    _password = field_validator("password")(valid_password)


def user_out(user: User, last_sign_in: datetime | None = None) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "fullName": user.full_name,
        "isActive": user.is_active,
        "role": {"id": user.role.id, "name": user.role.name},
        "createdAt": iso(user.created_at),
        "lastSignInAt": iso(last_sign_in),
    }


def get_user(db: DB, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such person.")
    return user


def check_role(db: DB, role_id: str) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise field_error("roleId", "Pick a role.")
    return role


def email_taken(db: DB, email: str, but: str | None = None) -> bool:
    q = select(User.id).where(func.lower(User.email) == email.lower())
    if but:
        q = q.where(User.id != but)
    return db.scalar(q) is not None


@router.get("/users")
def list_users(_: UsersPerm, db: DB) -> dict:
    last = dict(
        db.execute(
            select(SignInSession.user_id, func.max(SignInSession.created_at)).group_by(SignInSession.user_id)
        ).all()
    )
    users = db.scalars(select(User).order_by(User.is_active.desc(), func.lower(User.full_name))).all()
    roles = db.scalars(select(Role).order_by(Role.is_system.desc(), func.lower(Role.name))).all()
    return {
        "items": [user_out(u, last.get(u.id)) for u in users],
        "roles": [{"id": r.id, "name": r.name, "description": r.description} for r in roles],
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(_: UsersPerm, me: CurrentUser, db: DB, body: UserIn) -> dict:
    if email_taken(db, body.email):
        raise field_error("email", "Someone here already has that email.")
    check_role(db, body.role_id)
    user = User(
        email=body.email,
        full_name=body.full_name,
        role_id=body.role_id,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.flush()
    audit(db, me, "user.created", target=user.email, target_type="user", target_id=user.id)
    db.commit()
    return user_out(db.get(User, user.id))


@router.patch("/users/{user_id}")
def update_user(_: UsersPerm, me: CurrentUser, db: DB, user_id: str, body: UserPatch) -> dict:
    user = get_user(db, user_id)
    wanted = changed(body)
    for key in ("email", "full_name", "role_id", "is_active"):
        if key in wanted and wanted[key] is None:
            raise field_error(to_camel(key), "This can't be empty.")
    if wanted.get("is_active") is False and user.id == me.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You can't switch yourself off. Ask another admin.")
    if "email" in wanted and email_taken(db, wanted["email"], but=user.id):
        raise field_error("email", "Someone here already has that email.")
    if "role_id" in wanted:
        check_role(db, wanted["role_id"])

    fields = [k for k, v in wanted.items() if getattr(user, k) != v]
    for key in fields:
        setattr(user, key, wanted[key])
    if not fields:
        return user_out(user)
    keep_an_administrator(db)
    action = "user.updated"
    if fields == ["is_active"]:
        action = "user.switched_on" if user.is_active else "user.switched_off"
    audit(
        db,
        me,
        action,
        target=user.email,
        target_type="user",
        target_id=user.id,
        fields=[to_camel(f) for f in fields],
    )
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(_: UsersPerm, me: CurrentUser, db: DB, user_id: str, body: PasswordIn) -> Response:
    """A new password, set by an admin. Every session the person had ends."""
    user = get_user(db, user_id)
    user.password_hash = hash_password(body.password)
    user.password_changed_at = datetime.now(UTC)
    audit(db, me, "user.password_reset", target=user.email, target_type="user", target_id=user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Roles and Permissions --------------------------------------------------


def valid_permissions(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    unknown = sorted(set(value) - ALL_PERMISSIONS)
    if unknown:
        raise ValueError(f"Unknown permission: {', '.join(unknown)}.")
    return sorted(set(value))


class RoleIn(Api):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    permissions: list[str] = Field(default_factory=list, max_length=len(ALL_PERMISSIONS))

    _permissions = field_validator("permissions")(valid_permissions)


class RolePatch(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    permissions: list[str] | None = Field(None, max_length=len(ALL_PERMISSIONS))

    _permissions = field_validator("permissions")(valid_permissions)


def role_out(role: Role, users: int = 0) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "isSystem": role.is_system,
        "permissions": sorted(permissions_of(role)),
        "userCount": users,
    }


def role_users(db: DB) -> dict[str, int]:
    return dict(db.execute(select(User.role_id, func.count()).where(User.is_active).group_by(User.role_id)).all())


def get_role(db: DB, role_id: str) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such role.")
    return role


def name_taken(db: DB, name: str, but: str | None = None) -> bool:
    q = select(Role.id).where(func.lower(Role.name) == name.lower())
    if but:
        q = q.where(Role.id != but)
    return db.scalar(q) is not None


def set_grants(role: Role, permissions: list[str]) -> None:
    role.grants = [RolePermission(permission=p) for p in sorted(set(permissions))]


@router.get("/roles")
def list_roles(_: RolesPerm, db: DB) -> dict:
    counts = role_users(db)
    roles = db.scalars(select(Role).order_by(Role.is_system.desc(), func.lower(Role.name))).all()
    return {"roles": [role_out(r, counts.get(r.id, 0)) for r in roles], "catalogue": catalogue_out()}


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(_: RolesPerm, me: CurrentUser, db: DB, body: RoleIn) -> dict:
    if name_taken(db, body.name):
        raise field_error("name", "There's already a role with that name.")
    role = Role(name=body.name, description=body.description)
    set_grants(role, body.permissions)
    db.add(role)
    db.flush()
    audit(db, me, "role.created", target=role.name, target_type="role", target_id=role.id)
    db.commit()
    return role_out(role)


@router.patch("/roles/{role_id}")
def update_role(_: RolesPerm, me: CurrentUser, db: DB, role_id: str, body: RolePatch) -> dict:
    role = get_role(db, role_id)
    wanted = changed(body)
    if role.is_system and set(wanted) - {"description"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The Administrator role always has everything. Make a new role instead.",
        )
    if "name" in wanted and wanted["name"] is None:
        raise field_error("name", "Give the role a name.")
    if "name" in wanted and name_taken(db, wanted["name"], but=role.id):
        raise field_error("name", "There's already a role with that name.")

    fields = []
    for key in ("name", "description"):
        if key in wanted and (wanted[key] is not None or key == "description") and getattr(role, key) != wanted[key]:
            setattr(role, key, wanted[key])
            fields.append(key)
    if wanted.get("permissions") is not None and set(wanted["permissions"]) != role.permissions:
        set_grants(role, wanted["permissions"])
        fields.append("permissions")
    if fields:
        keep_an_administrator(db)
        audit(db, me, "role.updated", target=role.name, target_type="role", target_id=role.id, fields=fields)
        db.commit()
    return role_out(role, role_users(db).get(role.id, 0))


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(_: RolesPerm, me: CurrentUser, db: DB, role_id: str) -> Response:
    role = get_role(db, role_id)
    if role.is_system:
        raise HTTPException(status.HTTP_409_CONFLICT, "The Administrator role can't be deleted.")
    holders = db.scalar(select(func.count()).select_from(User).where(User.role_id == role.id)) or 0
    if holders:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{holders} {'person has' if holders == 1 else 'people have'} this role. Give them another one first.",
        )
    audit(db, me, "role.deleted", target=role.name, target_type="role", target_id=role.id)
    db.delete(role)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Activity Log (Audit) ---------------------------------------------------


@router.get("/audit")
def audit_log(
    _: AuditPerm,
    db: DB,
    before: int | None = Query(None, ge=1, description="the last id of the page before"),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = Query(None, max_length=64, description="an action, or its start: 'user.' for every user change"),
    actor_id: str | None = Query(None, max_length=36, alias="actorId"),
) -> dict:
    """Newest first. Pass the last entry's id as `before` for the next page."""
    q = select(AuditEntry).order_by(AuditEntry.id.desc()).limit(limit + 1)
    if before is not None:
        q = q.where(AuditEntry.id < before)
    if action:
        q = q.where(AuditEntry.action.startswith(action) if action.endswith(".") else AuditEntry.action == action)
    if actor_id:
        q = q.where(AuditEntry.actor_id == actor_id)
    entries = db.scalars(q).all()
    return {
        "items": [
            {
                "id": e.id,
                "at": iso(e.at),
                "actor": e.actor,
                "actorId": e.actor_id,
                "action": e.action,
                "target": e.target,
                "targetType": e.target_type,
                "targetId": e.target_id,
                "fields": e.fields or [],
            }
            for e in entries[:limit]
        ],
        "more": len(entries) > limit,
    }

