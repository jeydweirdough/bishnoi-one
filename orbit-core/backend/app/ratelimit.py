"""Rate limits: how much traffic one person, or one address, may send.

Token buckets, one per key and kind of request. A bucket holds `burst`
requests and refills at `per_minute`; each request takes one, and an empty
bucket answers 429 with Retry-After, so a burst of normal clicking never
trips it but a runaway loop or a scraper does.

Who a request counts against:
- signed in: the user id in the token. Every call reaches the API through the
  Next server, so counting by address would put the whole company in one
  bucket; counting by person keeps one heavy user from slowing everyone else.
- not signed in: the client's address, which the Next server passes on in
  X-Forwarded-For. It is believed only from a trusted proxy (a browser could
  send anything). When no client address is known, the request isn't limited
  by address, so one crowded office can't lock the others out; sign-in keeps
  its own per-email limit in app/routers/auth.py either way.

The buckets are in memory, per process. With several API workers or servers,
each counts on its own; move them to Redis then.
"""

import math
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.config import Settings
from app.security import read_token


@dataclass(frozen=True)
class Limit:
    per_minute: int
    burst: int


class Buckets:
    """Thread-safe token buckets keyed by anything hashable."""

    def __init__(self, max_keys: int = 50_000) -> None:
        self._state: dict[tuple, tuple[float, float]] = {}  # key -> (tokens, updated at)
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def take(self, key: tuple, limit: Limit, now: float | None = None) -> tuple[bool, int, float]:
        """(allowed, requests left, seconds until one more is allowed)."""
        now = time.monotonic() if now is None else now
        rate = limit.per_minute / 60
        with self._lock:
            tokens, at = self._state.get(key, (float(limit.burst), now))
            tokens = min(float(limit.burst), tokens + (now - at) * rate)
            if tokens >= 1:
                self._state[key] = (tokens - 1, now)
                allowed, wait = True, 0.0
            else:
                self._state[key] = (tokens, now)
                allowed, wait = False, (1 - tokens) / rate
            if len(self._state) > self._max_keys:
                self._forget_idle(now)
            return allowed, int(max(tokens - 1, 0)) if allowed else 0, wait

    def _forget_idle(self, now: float) -> None:
        # Buckets untouched for ten minutes are full again; dropping them changes nothing.
        for key in [k for k, (_, at) in self._state.items() if now - at > 600]:
            del self._state[key]


def kind_of(request: Request) -> str | None:
    """Which limit a request falls under; None for ones that aren't limited."""
    if request.url.path == "/health" or request.method == "OPTIONS":
        return None
    if request.url.path == "/auth/login":
        return "login"
    if request.method in ("GET", "HEAD"):
        return "read"
    if "/bulk/" in request.url.path:
        return "bulk"
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        return "upload"
    return "write"


def client_address(request: Request, trusted: set[str]) -> str | None:
    peer = request.client.host if request.client else None
    if peer in trusted:
        # From the Next server or a proxy: the first hop it saw is the client.
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        return forwarded or None
    return peer


def install(app: FastAPI, settings: Settings) -> None:
    buckets = Buckets()
    per_person = {
        "read": Limit(settings.rate_reads_per_minute, max(10, settings.rate_reads_per_minute // 3)),
        "write": Limit(settings.rate_writes_per_minute, max(5, settings.rate_writes_per_minute // 2)),
        "upload": Limit(settings.rate_uploads_per_minute, max(2, settings.rate_uploads_per_minute // 2)),
        # One bulk request is up to 500 items of work, queued; a few a minute is plenty.
        "bulk": Limit(settings.rate_bulk_per_minute, max(2, settings.rate_bulk_per_minute // 2)),
    }
    per_address = {
        "login": Limit(max(1, settings.rate_anonymous_per_minute // 2), max(3, settings.rate_anonymous_per_minute // 6)),
        "anonymous": Limit(settings.rate_anonymous_per_minute, max(5, settings.rate_anonymous_per_minute // 2)),
    }
    trusted = set(settings.trusted_proxies)
    app.state.rate_buckets = buckets

    @app.middleware("http")
    async def rate_limit(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        kind = kind_of(request) if settings.rate_limit_enabled else None
        if kind is None:
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        claims = read_token(settings, auth[7:]) if auth.lower().startswith("bearer ") else None
        if claims and kind != "login":
            key, limit = ("user", claims.user_id, kind), per_person[kind]
        else:
            address = client_address(request, trusted)
            if address is None:
                return await call_next(request)
            name = "login" if kind == "login" else "anonymous"
            key, limit = ("address", address, name), per_address[name]

        allowed, left, wait = buckets.take(key, limit)
        if not allowed:
            seconds = max(1, math.ceil(wait))
            return JSONResponse(
                {"detail": f"That's a lot of requests at once. Try again in {seconds} second{'s' if seconds > 1 else ''}."},
                status_code=429,
                headers={"Retry-After": str(seconds), "X-RateLimit-Limit": str(limit.per_minute), "X-RateLimit-Remaining": "0"},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit.per_minute)
        response.headers["X-RateLimit-Remaining"] = str(left)
        return response
