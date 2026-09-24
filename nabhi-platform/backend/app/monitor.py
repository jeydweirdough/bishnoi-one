"""Whether each application answers, and how fast (nbpl_health_checks).

The platform asks each application's health address (its API's /health) and
records the answer. It asks when someone looks and the last answer is out of
date (Settings > Monitoring), not on a timer: a serverless host (Vercel) runs
nothing between requests, so a timer would never fire there.

What a check makes of an answer:
- 2xx, quickly: operational. 2xx, slower than the slow mark: degraded.
- 503 from an app that couldn't start (app/server.py in each app says which
  setting to look at): down, with that setting named.
- Anything else, no answer, or no answer in time: down.

What people see is the check, unless a Platform Admin has declared otherwise
(maintenance, degraded, an outage the check can't see), which then wins.
"""

import logging
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.api import as_utc, iso
from app.models import Application, HealthCheck, Integration
from app.platform_settings import MonitoringSection

log = logging.getLogger("platform.monitor")

# The one "database" target: this platform's own.
DATABASE_ID = "platform-database"


@dataclass
class Answer:
    status: str
    ms: int | None
    http_status: int | None
    detail: str | None


def probe(url: str, timeout: float, slow_ms: int) -> Answer:
    """One look at one address. Replaced in tests, which have nothing to call."""
    started = time.perf_counter()
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=False, headers={"User-Agent": "nabhi-platform-monitor"})
    except httpx.TimeoutException:
        return Answer("down", None, None, f"No answer within {timeout:g} seconds.")
    except httpx.HTTPError:
        return Answer("down", None, None, "Not answering: nothing is listening at that address.")
    ms = round((time.perf_counter() - started) * 1000)
    body = _json(response)
    if response.status_code == 503 and isinstance(body, dict) and body.get("problem"):
        check = ", ".join(str(c) for c in body.get("check") or []) or "its logs"
        return Answer("down", ms, 503, f"It can't start ({body['problem']}): check {check}."[:300])
    if not 200 <= response.status_code < 300:
        return Answer("down", ms, response.status_code, f"Answered HTTP {response.status_code}.")
    if isinstance(body, dict) and body.get("ok") is False:
        return Answer("down", ms, response.status_code, "It answered, but says it isn't working.")
    if ms > slow_ms:
        return Answer("degraded", ms, response.status_code, f"Slow: {ms} ms to answer.")
    return Answer("operational", ms, response.status_code, None)


def _json(response: httpx.Response):
    try:
        return response.json()
    except ValueError:
        return None


def _database(db: Session, slow_ms: int) -> Answer:
    started = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 (any failure is "down"; its text may hold an address)
        log.exception("database check failed")
        return Answer("down", None, None, "The platform's database didn't answer.")
    ms = round((time.perf_counter() - started) * 1000)
    return Answer("degraded" if ms > slow_ms else "operational", ms, None, f"Slow: {ms} ms." if ms > slow_ms else None)


def last_checked(db: Session) -> datetime | None:
    moment = db.scalar(select(func.max(HealthCheck.checked_at)))
    return as_utc(moment) if moment else None


def is_stale(db: Session, config: MonitoringSection) -> bool:
    last = last_checked(db)
    return last is None or datetime.now(UTC) - last > timedelta(seconds=config.stale_seconds)


def check_all(db: Session, config: MonitoringSection) -> None:
    """Asks every active application and every integration with an address,
    at once, and writes down what each said. The caller commits."""
    apps = db.scalars(select(Application).where(Application.is_active, Application.health_url.is_not(None))).all()
    links = db.scalars(
        select(Integration).join(Application).where(Application.is_active, Integration.health_url.is_not(None))
    ).all()
    targets = [("application", a.id, a.health_url) for a in apps] + [("integration", i.id, i.health_url) for i in links]
    answers: list[Answer] = []
    if targets:
        with ThreadPoolExecutor(max_workers=min(8, len(targets))) as pool:
            answers = list(pool.map(lambda t: probe(t[2], config.timeout_seconds, config.slow_ms), targets))
    now = datetime.now(UTC)
    integrations = {i.id: i for i in links}
    for (kind, target_id, _), answer in zip(targets, answers, strict=True):
        db.add(HealthCheck(target_kind=kind, target_id=target_id, checked_at=now, **answer.__dict__))
        # What an integration with an address shows is what its check said.
        if kind == "integration":
            integrations[target_id].status = answer.status
    database = _database(db, config.slow_ms)
    db.add(HealthCheck(target_kind="database", target_id=DATABASE_ID, checked_at=now, **database.__dict__))
    db.execute(delete(HealthCheck).where(HealthCheck.checked_at < now - timedelta(days=config.keep_days)))


def ensure_fresh(db: Session, config: MonitoringSection, force: bool = False) -> None:
    if force or is_stale(db, config):
        check_all(db, config)
        db.commit()


def latest(db: Session, kind: str, ids: Iterable[str] | None = None) -> dict[str, HealthCheck]:
    """The newest check of each target of one kind."""
    newest = (
        select(HealthCheck.target_id, func.max(HealthCheck.checked_at).label("at"))
        .where(HealthCheck.target_kind == kind)
        .group_by(HealthCheck.target_id)
    )
    if ids is not None:
        newest = newest.where(HealthCheck.target_id.in_(list(ids)))
    newest = newest.subquery()
    rows = db.scalars(
        select(HealthCheck).join(
            newest, (HealthCheck.target_id == newest.c.target_id) & (HealthCheck.checked_at == newest.c.at)
        ).where(HealthCheck.target_kind == kind)
    ).all()
    return {r.target_id: r for r in rows}


def uptime(db: Session, kind: str, hours: int = 24) -> dict[str, float]:
    """The share of checks that weren't down, per target, over the last hours."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    rows = db.execute(
        select(HealthCheck.target_id, HealthCheck.status, func.count())
        .where(HealthCheck.target_kind == kind, HealthCheck.checked_at >= since)
        .group_by(HealthCheck.target_id, HealthCheck.status)
    ).all()
    totals: dict[str, list[int]] = {}
    for target_id, status, n in rows:
        up_down = totals.setdefault(target_id, [0, 0])
        up_down[0 if status != "down" else 1] += n
    return {t: round(100 * up / (up + down), 1) for t, (up, down) in totals.items() if up + down}


def app_status(app: Application, check: HealthCheck | None) -> str:
    """What the screens say about an application: operational, degraded, down,
    maintenance, unknown (never checked, or nowhere to ask) or retired."""
    if not app.is_active:
        return "retired"
    if app.status_override:
        return {"outage": "down"}.get(app.status_override, app.status_override)
    if check is None or not app.health_url:
        return "unknown"
    return check.status


def check_out(check: HealthCheck | None) -> dict | None:
    if check is None:
        return None
    return {"status": check.status, "ms": check.ms, "httpStatus": check.http_status, "detail": check.detail, "checkedAt": iso(check.checked_at)}
