"""What keeps the API up and its answers safe, whatever arrives.

- Every request gets a reference (X-Request-ID), so a person can quote it and
  the log line can be found.
- Too many requests from one person (or one address, before sign-in) are
  turned away with 429 and how long to wait, before any work is done.
- A request bigger than the API takes is turned away with 413, counted as it
  arrives, so a huge upload can't fill the memory.
- An error nobody planned for answers in plain words with its reference,
  never with its text: that may name a table, a file or a setting. The full
  error goes to the log. A database that isn't answering says so (503, with
  when to try again), rather than looking like a fault.

Limits come from the environment, so a host can loosen or tighten them
without a deploy: RATE_LIMIT_PER_MINUTE, RATE_LIMIT_WRITES_PER_MINUTE,
RATE_LIMIT_ANONYMOUS_PER_MINUTE, MAX_REQUEST_MB.

The same file is in every app's API (app/guard.py).
"""

import hashlib
import logging
import os
import threading
import time
import uuid
from collections import deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError as PoolTimeout

log = logging.getLogger("bishnoi.guard")

WRITES = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Answered without counting: the host's checks, and the browser's preflight.
FREE_PATHS = frozenset({"/health", "/"})


def _number(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


class Window:
    """Requests in the last minute, per key. In memory: each server counts its own."""

    def __init__(self) -> None:
        self._seen: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._swept = time.monotonic()

    def take(self, key: str, limit: int, now: float) -> int:
        """0 if the request may go ahead, else the seconds until it may."""
        with self._lock:
            if now - self._swept > 60:
                # Forget whoever has gone quiet, so the table can't grow without end.
                for k in [k for k, q in self._seen.items() if not q or now - q[-1] > 60]:
                    del self._seen[k]
                self._swept = now
            seen = self._seen.setdefault(key, deque())
            while seen and now - seen[0] >= 60:
                seen.popleft()
            if len(seen) >= limit:
                return max(1, int(60 - (now - seen[0])) + 1)
            seen.append(now)
            return 0


def _who(request: Request) -> tuple[str, bool]:
    """Whose request this is: the signed-in person (by their token, never kept as
    such), else the address it came from. True when signed in."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and len(auth) > 20:
        return "t:" + hashlib.sha256(auth[7:].encode()).hexdigest()[:24], True
    # Behind a host's proxy (Vercel) the first forwarded address is the person's;
    # the screens' server passes it on (src/platform/lib/api.ts).
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    peer = request.client.host if request.client else "?"
    return "a:" + (forwarded or peer), False


def _reference(request: Request) -> str:
    return getattr(request.state, "reference", None) or uuid.uuid4().hex[:12]


def _answer(request: Request, status: int, detail: str, **headers: str) -> JSONResponse:
    reference = _reference(request)
    return JSONResponse({"detail": detail, "reference": reference}, status_code=status, headers={"X-Request-ID": reference, **headers})


class _TooBig(Exception):
    pass


def install(app: FastAPI, name: str) -> None:
    """Put the guard around this app. Call it first, just after the app is made:
    the CORS and host checks added after it then wrap it, so even a refusal
    carries the headers a browser needs to read it."""
    per_minute = _number("RATE_LIMIT_PER_MINUTE", 600)
    writes_per_minute = _number("RATE_LIMIT_WRITES_PER_MINUTE", 120)
    anonymous_per_minute = _number("RATE_LIMIT_ANONYMOUS_PER_MINUTE", 120)
    largest = _number("MAX_REQUEST_MB", 12) * 1024 * 1024
    window = Window()

    @app.exception_handler(OperationalError)
    @app.exception_handler(PoolTimeout)
    async def _database_away(request: Request, error: Exception) -> JSONResponse:
        log.warning("%s %s: database not answering (%s) [%s]", request.method, request.url.path, type(error).__name__, _reference(request))
        return _answer(request, 503, "The database isn't answering just now. Try again in a few seconds.", **{"Retry-After": "5"})

    @app.exception_handler(DBAPIError)
    async def _database_refused(request: Request, error: Exception) -> JSONResponse:
        log.exception("%s %s: database error [%s]", request.method, request.url.path, _reference(request), exc_info=error)
        return _answer(request, 500, f"Something went wrong saving or reading this. Try again; if it keeps happening, give the support team this reference: {_reference(request)}.")

    @app.exception_handler(Exception)
    async def _unplanned(request: Request, error: Exception) -> JSONResponse:
        log.exception("%s %s: unexpected error [%s]", request.method, request.url.path, _reference(request), exc_info=error)
        return _answer(request, 500, f"Something went wrong on our side. Try again; if it keeps happening, give the support team this reference: {_reference(request)}.")

    class Guard:
        """Pure ASGI, so a refused request costs almost nothing and uploads are counted as they stream."""

        def __init__(self, inner) -> None:
            self.inner = inner

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                return await self.inner(scope, receive, send)
            request = Request(scope)
            reference = (request.headers.get("x-request-id") or "")[:40]
            # A reference from outside is used only if it's plainly one of ours.
            reference = reference if reference.isalnum() and len(reference) >= 8 else uuid.uuid4().hex[:12]
            scope.setdefault("state", {})["reference"] = reference

            async def send_with_reference(message):
                if message["type"] == "http.response.start":
                    message.setdefault("headers", []).append((b"x-request-id", reference.encode()))
                await send(message)

            method = scope.get("method", "GET")
            if method != "OPTIONS" and scope.get("path") not in FREE_PATHS:
                key, signed_in = _who(request)
                now = time.monotonic()
                wait = window.take(key, per_minute if signed_in else anonymous_per_minute, now)
                if not wait and method in WRITES:
                    wait = window.take(key + ":w", writes_per_minute, now)
                if wait:
                    log.warning("%s %s: too many requests from %s… [%s]", method, scope.get("path"), key[:10], reference)
                    response = _answer(request, 429, f"That's a lot of requests in a short time. Wait {wait} seconds and try again.", **{"Retry-After": str(wait)})
                    return await response(scope, receive, send)

            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > largest:
                response = _answer(request, 413, f"That's more than the {largest // (1024 * 1024)} MB that can be sent at once. Send a smaller file, or fewer at a time.")
                return await response(scope, receive, send)

            received = 0

            async def counted():
                nonlocal received
                message = await receive()
                if message["type"] == "http.request":
                    received += len(message.get("body", b""))
                    if received > largest:
                        raise _TooBig
                return message

            try:
                await self.inner(scope, counted, send_with_reference)
            except _TooBig:
                response = _answer(request, 413, f"That's more than the {largest // (1024 * 1024)} MB that can be sent at once. Send a smaller file, or fewer at a time.")
                await response(scope, receive, send)

    app.add_middleware(Guard)
    log.info("%s: guard on (%s a minute signed in, %s writes, %s before sign-in; up to %s MB a request)", name, per_minute, writes_per_minute, anonymous_per_minute, largest // (1024 * 1024))
