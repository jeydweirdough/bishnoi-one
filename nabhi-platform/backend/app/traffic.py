"""The Platform API's own traffic, one row per minute (nbpl_traffic).

Each request is counted in memory, and the counts are added to the database
every few seconds rather than once per request. Several copies of the API
(Vercel starts one per burst) each add their own counts to the same minute, so
the totals come out right however many are running. A copy that stops loses
at most its last few seconds.

The other applications' traffic isn't here: each keeps its own. What the
platform sees of them is how fast they answer a health check (app/monitor.py).
"""

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import TrafficMinute

FLUSH_EVERY = 10.0  # seconds


@dataclass
class _Bucket:
    requests: int = 0
    refused: int = 0
    failed: int = 0
    total_ms: int = 0
    max_ms: int = 0


class Traffic:
    def __init__(self) -> None:
        self._buckets: dict[datetime, _Bucket] = {}
        self._lock = threading.Lock()
        self._flushed = time.monotonic()

    def count(self, status_code: int, ms: int) -> None:
        minute = datetime.now(UTC).replace(second=0, microsecond=0)
        with self._lock:
            b = self._buckets.setdefault(minute, _Bucket())
            b.requests += 1
            b.refused += 400 <= status_code < 500
            b.failed += status_code >= 500
            b.total_ms += ms
            b.max_ms = max(b.max_ms, ms)

    def due(self) -> bool:
        return time.monotonic() - self._flushed >= FLUSH_EVERY

    def flush(self, sessions: sessionmaker[Session]) -> None:
        with self._lock:
            buckets, self._buckets = self._buckets, {}
            self._flushed = time.monotonic()
        if not buckets:
            return
        with sessions() as db:
            for minute, b in buckets.items():
                _add(db, minute, b)
            db.commit()

    def clear(self) -> None:
        with self._lock:
            self._buckets = {}


def _add(db: Session, minute: datetime, b: _Bucket) -> None:
    increments = dict(
        requests=TrafficMinute.requests + b.requests,
        refused=TrafficMinute.refused + b.refused,
        failed=TrafficMinute.failed + b.failed,
        total_ms=TrafficMinute.total_ms + b.total_ms,
        max_ms=case((TrafficMinute.max_ms < b.max_ms, b.max_ms), else_=TrafficMinute.max_ms),
    )
    for _ in range(2):
        if db.execute(update(TrafficMinute).where(TrafficMinute.minute == minute).values(**increments)).rowcount:
            return
        try:
            with db.begin_nested():
                db.add(TrafficMinute(minute=minute, requests=b.requests, refused=b.refused, failed=b.failed, total_ms=b.total_ms, max_ms=b.max_ms))
            return
        except IntegrityError:
            continue  # another copy made the row first; add to it instead


def prune(db: Session, keep_days: int) -> None:
    db.execute(delete(TrafficMinute).where(TrafficMinute.minute < datetime.now(UTC) - timedelta(days=keep_days)))


traffic = Traffic()
