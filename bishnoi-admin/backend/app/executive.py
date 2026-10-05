"""Executive Office & Administration domain logic, countdown engine, and proactive alerts."""

from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    ComplianceRecord,
    CorporateDocument,
    ImmigrationRecord,
    Notification,
    PropertyRecord,
    Ticket,
    TicketUpdate,
    new_id,
    utcnow,
)


def safe_tz(name: str):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        if "Manila" in name:
            return timezone(timedelta(hours=8))
        return UTC


def today_in_org(settings: Settings) -> date:
    return datetime.now(safe_tz(settings.org_timezone)).date()



def calculate_days_remaining(due_dt: datetime | None, settings: Settings) -> int | None:
    if due_dt is None:
        return None
    today = today_in_org(settings)
    due_date = due_dt.date() if isinstance(due_dt, datetime) else due_dt
    return (due_date - today).days


def urgency_tier(days: int | None) -> str:
    if days is None:
        return "none"
    if days < 0:
        return "overdue"
    if days <= 15:
        return "urgent"
    if days <= 30:
        return "approaching"
    if days <= 60:
        return "upcoming"
    return "good_standing"


def severity_from_days(days: int) -> str:
    if days < 0:
        return "critical"
    if days <= 15:
        return "urgent"
    if days <= 45:
        return "warning"
    return "info"


def sync_notifications(db: Session, settings: Settings) -> int:
    """Scans all expiring registrations, visas, contracts, leases, and SLA tickets,

    generating or updating proactive notifications.
    """
    today = today_in_org(settings)
    count = 0

    # 1. Compliance / Permits (BOC, SEC, BIR, LGU, FDA)
    permits = db.scalars(select(ComplianceRecord).where(ComplianceRecord.status != "closed")).all()
    for p in permits:
        days = (p.expiration_date.date() - today).days
        if days <= max(90, p.renewal_window_days):
            existing = db.scalar(
                select(Notification).where(
                    Notification.entity_type == "permit",
                    Notification.entity_id == p.id,
                    Notification.is_resolved.is_(False),
                )
            )
            title = f"{p.agency}: {p.title}"
            severity = severity_from_days(days)
            msg = (
                f"OVERDUE by {abs(days)} day(s)! Immediate renewal required with {p.agency}."
                if days < 0
                else f"Expires in {days} day(s) (target: {p.expiration_date.strftime('%b %d, %Y')}). Renewal window open."
            )
            if existing:
                existing.days_remaining = days
                existing.severity = severity
                existing.message = msg
                existing.title = title
                existing.due_date = p.expiration_date
                existing.updated_at = utcnow()
            else:
                db.add(
                    Notification(
                        id=new_id(),
                        entity_type="permit",
                        entity_id=p.id,
                        severity=severity,
                        title=title,
                        message=msg,
                        days_remaining=days,
                        due_date=p.expiration_date,
                    )
                )
                count += 1

    # 2. Expatriate & Immigration (ACR, AEP, Visas, Passports)
    immigrants = db.scalars(select(ImmigrationRecord).where(ImmigrationRecord.status != "expired_closed")).all()
    for im in immigrants:
        days = (im.expiration_date.date() - today).days
        if days <= max(90, im.renewal_lead_days):
            existing = db.scalar(
                select(Notification).where(
                    Notification.entity_type == "immigration",
                    Notification.entity_id == im.id,
                    Notification.is_resolved.is_(False),
                )
            )
            doc_label = {
                "visa": "Visa",
                "acr_card": "ACR I-Card",
                "aep_permit": "DOLE AEP",
                "passport": "Passport",
                "exec_id": "Executive ID",
            }.get(im.document_type, im.document_type.upper())
            title = f"{doc_label}: {im.individual_name}"
            severity = severity_from_days(days)
            msg = (
                f"EXPIRED by {abs(days)} day(s)! {im.individual_name} ({im.designation}) requires immediate regularisation."
                if days < 0
                else f"{doc_label} #{im.document_number} expires in {days} day(s). Bureau filing needed."
            )
            if existing:
                existing.days_remaining = days
                existing.severity = severity
                existing.message = msg
                existing.title = title
                existing.due_date = im.expiration_date
                existing.updated_at = utcnow()
            else:
                db.add(
                    Notification(
                        id=new_id(),
                        entity_type="immigration",
                        entity_id=im.id,
                        severity=severity,
                        title=title,
                        message=msg,
                        days_remaining=days,
                        due_date=im.expiration_date,
                    )
                )
                count += 1

    # 3. Corporate Documents & Insurances (D&O, Contracts, Leases, NDAs)
    docs = db.scalars(
        select(CorporateDocument).where(
            CorporateDocument.expiration_date.is_not(None),
            CorporateDocument.status != "terminated",
        )
    ).all()
    for d in docs:
        if d.expiration_date:
            days = (d.expiration_date.date() - today).days
            if days <= max(60, d.notice_period_days):
                existing = db.scalar(
                    select(Notification).where(
                        Notification.entity_type == "document",
                        Notification.entity_id == d.id,
                        Notification.is_resolved.is_(False),
                    )
                )
                title = f"Document: {d.title}"
                severity = severity_from_days(days)
                msg = (
                    f"Expired {abs(days)} day(s) ago ({d.counterparty})."
                    if days < 0
                    else f"Renewal / Notice deadline in {days} day(s). Counterparty: {d.counterparty}."
                )
                if existing:
                    existing.days_remaining = days
                    existing.severity = severity
                    existing.message = msg
                    existing.title = title
                    existing.due_date = d.expiration_date
                    existing.updated_at = utcnow()
                else:
                    db.add(
                        Notification(
                            id=new_id(),
                            entity_type="document",
                            entity_id=d.id,
                            severity=severity,
                            title=title,
                            message=msg,
                            days_remaining=days,
                            due_date=d.expiration_date,
                        )
                    )
                    count += 1

    # 4. Properties & Facilities (Office Leases, Warehouses, Utilities)
    props = db.scalars(select(PropertyRecord).where(PropertyRecord.status != "terminated")).all()
    for pr in props:
        days = (pr.lease_end.date() - today).days
        if days <= max(90, pr.notice_deadline_days):
            existing = db.scalar(
                select(Notification).where(
                    Notification.entity_type == "property",
                    Notification.entity_id == pr.id,
                    Notification.is_resolved.is_(False),
                )
            )
            title = f"Lease Renewal: {pr.name}"
            severity = severity_from_days(days)
            msg = (
                f"Lease ended {abs(days)} day(s) ago! Contact lessor {pr.lessor_name}."
                if days < 0
                else f"Lease option notice decision required in {days} day(s). Lessor: {pr.lessor_name}."
            )
            if existing:
                existing.days_remaining = days
                existing.severity = severity
                existing.message = msg
                existing.title = title
                existing.due_date = pr.lease_end
                existing.updated_at = utcnow()
            else:
                db.add(
                    Notification(
                        id=new_id(),
                        entity_type="property",
                        entity_id=pr.id,
                        severity=severity,
                        title=title,
                        message=msg,
                        days_remaining=days,
                        due_date=pr.lease_end,
                    )
                )
                count += 1

    # 5. Urgent or SLA-breaching Office Tickets
    tickets = db.scalars(select(Ticket).where(Ticket.status.in_(["open", "in_progress", "pending_vendor"]))).all()
    for tk in tickets:
        if tk.sla_due_date:
            days = (tk.sla_due_date.date() - today).days
            if days <= 2:  # 48 hours or overdue
                existing = db.scalar(
                    select(Notification).where(
                        Notification.entity_type == "ticket",
                        Notification.entity_id == tk.id,
                        Notification.is_resolved.is_(False),
                    )
                )
                title = f"Ticket {tk.ticket_number}: {tk.title}"
                severity = "critical" if days < 0 else "urgent"
                msg = (
                    f"SLA OVERDUE by {abs(days)} day(s)! Priority: {tk.priority.upper()}. Requester: {tk.requester_name}."
                    if days < 0
                    else f"Target SLA completion within {days} day(s). Assigned: {tk.assigned_to or 'Unassigned'}."
                )
                if existing:
                    existing.days_remaining = days
                    existing.severity = severity
                    existing.message = msg
                    existing.title = title
                    existing.due_date = tk.sla_due_date
                    existing.updated_at = utcnow()
                else:
                    db.add(
                        Notification(
                            id=new_id(),
                            entity_type="ticket",
                            entity_id=tk.id,
                            severity=severity,
                            title=title,
                            message=msg,
                            days_remaining=days,
                            due_date=tk.sla_due_date,
                        )
                    )
                    count += 1

    db.commit()
    return count
