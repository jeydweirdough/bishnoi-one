"""System monitoring: platform, application, API, database and integration
health, and the Platform API's traffic.

Health is asked for when someone looks and the last answer is out of date
(app/monitor.py); `refresh=true` asks now. Traffic is the Platform API's own
(app/traffic.py): each application counts its own requests, so what the
platform shows of them is how fast each answers its health check.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from app import monitor, platform_settings
from app.api import as_utc, iso
from app.deps import DB, CurrentUser, SettingsDep
from app.models import Application, HealthCheck, Integration, SignInSession, TrafficMinute
from app.traffic import traffic

router = APIRouter(prefix="/platform", tags=["monitoring"])


def traffic_summary(db, minutes: int = 60) -> dict:
    """Requests over the last `minutes`, with the last five for "per minute"."""
    now = datetime.now(UTC)
    rows = db.scalars(select(TrafficMinute).where(TrafficMinute.minute >= now - timedelta(minutes=minutes))).all()
    recent = [r for r in rows if as_utc(r.minute) >= now - timedelta(minutes=5)]
    requests = sum(r.requests for r in rows)
    failed = sum(r.failed for r in rows)
    return {
        "requestsPerMinute": round(sum(r.requests for r in recent) / 5, 1),
        "requests": requests,
        "refused": sum(r.refused for r in rows),
        "failed": failed,
        "failedPercent": round(100 * failed / requests, 2) if requests else 0.0,
        "averageMs": round(sum(r.total_ms for r in rows) / requests) if requests else None,
        "slowestMs": max((r.max_ms for r in rows), default=None),
        "activeSessions": db.scalar(
            select(func.count()).select_from(SignInSession).where(SignInSession.revoked_at.is_(None), SignInSession.expires_at > now)
        ),
    }


def health(db, settings, refresh: bool = False) -> dict:
    config = platform_settings.monitoring(db, settings)
    monitor.ensure_fresh(db, config, force=refresh)
    apps = db.scalars(select(Application).where(Application.is_active).order_by(Application.sort_order, Application.name)).all()
    checks = monitor.latest(db, "application", [a.id for a in apps])
    up = monitor.uptime(db, "application")
    links = db.execute(
        select(Integration, Application.name).join(Application).where(Application.is_active).order_by(Application.sort_order, Integration.name)
    ).all()
    link_checks = monitor.latest(db, "integration", [i.id for i, _ in links])
    database = monitor.latest(db, "database", [monitor.DATABASE_ID]).get(monitor.DATABASE_ID)
    last = traffic_summary(db, 15)
    # The Platform API is answering this very request; what can be wrong with
    # it is failing requests.
    api_status = "degraded" if last["failedPercent"] >= 5 else "operational"
    applications = [
        {"id": a.id, "key": a.key, "name": a.name, "status": monitor.app_status(a, checks.get(a.id)), "statusNote": a.status_note,
         "uptime": up.get(a.id), "lastCheck": monitor.check_out(checks.get(a.id)), "monitored": bool(a.health_url)}
        for a in apps
    ]
    worst = {s["status"] for s in applications} | {api_status, database.status if database else "operational"}
    overall = "down" if "down" in worst else "degraded" if worst & {"degraded", "maintenance"} else "operational"
    return {
        "overall": overall,
        "checkedAt": iso(monitor.last_checked(db)),
        "staleSeconds": config.stale_seconds,
        "platformApi": {"status": api_status, "failedPercent": last["failedPercent"], "averageMs": last["averageMs"]},
        "database": {"status": database.status if database else "unknown", **(monitor.check_out(database) or {})},
        "applications": applications,
        "integrations": [
            {"id": i.id, "name": i.name, "applicationName": name, "target": i.target, "status": i.status,
             "monitored": bool(i.health_url), "lastCheck": monitor.check_out(link_checks.get(i.id))}
            for i, name in links
        ],
    }


@router.get("/monitoring")
def monitoring(db: DB, settings: SettingsDep, _: CurrentUser, refresh: bool = False) -> dict:
    return health(db, settings, refresh)


@router.get("/monitoring/history")
def history(db: DB, _: CurrentUser, target_kind: str = "application", target_id: str | None = None, hours: int = 24) -> dict:
    since = datetime.now(UTC) - timedelta(hours=max(1, min(hours, 24 * 30)))
    query = select(HealthCheck).where(HealthCheck.target_kind == target_kind, HealthCheck.checked_at >= since)
    if target_id:
        query = query.where(HealthCheck.target_id == target_id)
    rows = db.scalars(query.order_by(HealthCheck.checked_at.desc()).limit(500)).all()
    return {"checks": [{"targetId": r.target_id, **monitor.check_out(r)} for r in rows]}


@router.get("/traffic")
def traffic_view(request: Request, db: DB, _: CurrentUser, hours: int = 6) -> dict:
    """Minute by minute (grouped to fit about 60 bars), and the totals."""
    traffic.flush(request.app.state.sessions)
    hours = max(1, min(hours, 24 * 7))
    now = datetime.now(UTC)
    rows = db.scalars(select(TrafficMinute).where(TrafficMinute.minute >= now - timedelta(hours=hours)).order_by(TrafficMinute.minute)).all()
    step = max(1, hours * 60 // 60)  # minutes per bar
    bars: dict[datetime, dict] = {}
    for r in rows:
        minute = as_utc(r.minute)
        start = minute - timedelta(minutes=(minute.hour * 60 + minute.minute) % step)
        b = bars.setdefault(start, {"at": iso(start), "requests": 0, "refused": 0, "failed": 0, "totalMs": 0})
        b["requests"] += r.requests
        b["refused"] += r.refused
        b["failed"] += r.failed
        b["totalMs"] += r.total_ms
    series = [
        {"at": b["at"], "requests": b["requests"], "refused": b["refused"], "failed": b["failed"],
         "averageMs": round(b["totalMs"] / b["requests"]) if b["requests"] else None}
        for b in bars.values()
    ]
    apps = db.scalars(select(Application).where(Application.is_active).order_by(Application.sort_order)).all()
    checks = monitor.latest(db, "application", [a.id for a in apps])
    response_times = [
        {"id": a.id, "name": a.name, "ms": checks[a.id].ms if a.id in checks else None, "status": monitor.app_status(a, checks.get(a.id))}
        for a in apps
    ]
    return {"hours": hours, "minutesPerBar": step, "summary": traffic_summary(db, hours * 60), "series": series,
            "applicationResponse": response_times}
