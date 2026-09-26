"""The dashboard: what is happening across the whole platform right now.
And the short lists the screens' pickers need (companies, applications,
staff, open incidents), in one call.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from app import platform_settings
from app.api import iso
from app.deps import DB, CurrentUser, SettingsDep
from app.models import TICKET_STATUSES, AccessRequest, Application, AuditEntry, Company, Identity, Incident, Ticket, User
from app.routers.activity import entry_out
from app.routers.communications import names_for as notice_names, notice_out, state_of
from app.routers.incidents import _companies, _names, incident_out
from app.routers.monitoring import health, traffic_summary
from app.routers.support import names_for, overdue_after, ticket_out
from app.traffic import traffic

router = APIRouter(prefix="/platform", tags=["dashboard"])

OPEN = [s for s in TICKET_STATUSES if s not in ("resolved", "closed")]
SEVERITY_RANK = {"minor": 1, "major": 2, "critical": 3}


def count(db, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


def banner_incidents(db, settings) -> list[Incident]:
    """Active incidents at least as severe as Settings > Notifications says."""
    floor = SEVERITY_RANK[platform_settings.notifications(db, settings).banner_severity]
    active = db.scalars(select(Incident).where(Incident.status != "resolved").order_by(Incident.started_at.desc())).all()
    return [i for i in active if SEVERITY_RANK[i.severity] >= floor]


@router.get("/dashboard")
def dashboard(request: Request, db: DB, settings: SettingsDep, _: CurrentUser) -> dict:
    traffic.flush(request.app.state.sessions)
    now = datetime.now(UTC)
    open_tickets = db.scalars(select(Ticket).where(Ticket.status.in_(OPEN))).all()
    limits = overdue_after(db, settings)
    overdue = sorted(
        (t for t in open_tickets if ticket_out(t, {}, limits)["isOverdue"]), key=lambda t: t.created_at
    )[:8]
    support = {
        "criticalBugs": sum(t.kind == "bug" and t.severity == "critical" for t in open_tickets),
        "bugs": sum(t.kind == "bug" for t in open_tickets),
        "complaints": sum(t.kind == "complaint" for t in open_tickets),
        "issues": sum(t.kind == "issue" for t in open_tickets),
        "features": sum(t.kind == "feature" for t in open_tickets),
        "support": sum(t.kind == "support" for t in open_tickets),
        "unassigned": sum(t.assignee_id is None for t in open_tickets),
        "overdue": sum(ticket_out(t, {}, limits)["isOverdue"] for t in open_tickets),
    }
    active = db.scalars(select(Incident).where(Incident.status != "resolved").order_by(Incident.started_at.desc())).all()
    names = _names(db, active)
    companies = _companies(db, [i.id for i in active])
    notices = sorted(
        (n for n in request.app.state.notices.all() if state_of(n, now) in ("showing", "scheduled")),
        key=lambda n: n["startsAt"],
    )[:5]
    recent = db.scalars(select(AuditEntry).order_by(AuditEntry.created_at.desc()).limit(10)).all()
    return {
        "counts": {
            "companies": count(db, Company),
            "activeCompanies": count(db, Company, Company.status == "active"),
            "users": count(db, Identity),
            "activeUsers": count(db, Identity, Identity.status == "active"),
            "applications": count(db, Application, Application.is_active),
            "openTickets": len(open_tickets),
            "activeIncidents": len(active),
            "pendingRequests": count(db, AccessRequest, AccessRequest.status == "pending"),
        },
        "health": health(db, settings),
        "traffic": traffic_summary(db, 60),
        "support": support,
        "overdue": [ticket_out(t, names_for(db, overdue), limits) for t in overdue],
        "incidents": [incident_out(i, names, companies.get(i.id, [])) for i in active],
        "notices": [notice_out(n, notice_names(db, notices)) for n in notices],
        "recent": [entry_out(e) for e in recent],
    }


@router.get("/banner")
def banner(db: DB, settings: SettingsDep, _: CurrentUser) -> dict:
    """What every screen shows at its top: the incidents serious enough."""
    incidents = banner_incidents(db, settings)
    names = _names(db, incidents)
    return {"incidents": [incident_out(i, names, []) for i in incidents]}


@router.get("/options")
def options(db: DB, _: CurrentUser) -> dict:
    return {
        "companies": [{"id": c.id, "name": c.name, "status": c.status}
                      for c in db.scalars(select(Company).order_by(func.lower(Company.name)))],
        "applications": [{"id": a.id, "key": a.key, "name": a.name}
                         for a in db.scalars(select(Application).where(Application.is_active).order_by(Application.sort_order))],
        "staff": [{"id": u.id, "name": u.full_name} for u in db.scalars(select(User).where(User.is_active).order_by(User.full_name))],
        "incidents": [{"id": i.id, "name": f"{i.number} {i.title}"}
                      for i in db.scalars(select(Incident).where(Incident.status != "resolved").order_by(Incident.started_at.desc()))],
        "now": iso(datetime.now(UTC)),
    }
