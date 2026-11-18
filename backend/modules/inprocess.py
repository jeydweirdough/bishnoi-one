"""Modules calling each other inside the one backend (stage M2, 2026-11-18).

Every module is part of one process (backend/main.py), so a module asking another one no longer
goes out to the network and back: the request is handed to the other module's app directly, as
an ASGI call, and answered the same way (same routes, checks, payloads and signed passes).

    inprocess.get("crm", url, params=..., headers=..., timeout=5)      # like httpx.get
    inprocess.post("platform", url, json=..., timeout=10)              # like httpx.post
    inprocess.request("exec", "PATCH", url, json=...)                  # like httpx.request
    with inprocess.urlopen("finance", urllib_request, timeout=10) as r: # like urllib.request.urlopen
        r.read()

The first argument is the caller's key on the Platform (crm, inventory, finance, exec, pharmacy,
platform...). A URL under BACKEND_URL + a registered module's path is served in-process; any other
URL (an outside server, a module set to an address of its own) and every call while nothing is
registered (each module's tests, a module run alone) goes over HTTP exactly as before, through
httpx / urllib looked up at call time (so tests that stand in for them still work).

Trust: an in-process request carries scope[MARK] = the caller's key. Only this file sets it; a
request from outside comes through backend/main.py, which takes the key out of every scope it
passes on, and no header is ever read for it. A module's key check (X-Bishnoi-Key for another
module, X-Bishnoi-App-Key for the Platform) takes `caller(request)` as that app instead of a key,
so modules in the one backend need no connection keys. Keys given still work (modules outside it).
"""

from __future__ import annotations

import http.client
import io
import logging
import threading
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

import anyio
import anyio.from_thread
import httpx

log = logging.getLogger("bishnoi.inprocess")

MARK = "bishnoi.internal"

ASGIApp = Callable[[MutableMapping[str, Any], Callable, Callable], Awaitable[None]]

_lock = threading.Lock()
_base: str | None = None  # BACKEND_URL, normalised
_apps: dict[str, tuple[str, ASGIApp]] = {}  # path (/crm) -> (Platform key, app)


def _norm(url: str) -> str:
    url = url.strip().rstrip("/")
    return url.replace("://localhost", "://127.0.0.1", 1)


def register(backend_url: str, key: str, path: str, app: ASGIApp) -> None:
    """main.py: this module's app answers BACKEND_URL + path in-process."""
    global _base
    with _lock:
        _base = _norm(backend_url)
        _apps[path.rstrip("/")] = (key, app)


def clear() -> None:
    """Nothing in-process any more (tests)."""
    global _base
    with _lock:
        _base = None
        _apps.clear()


def registered() -> dict[str, str]:
    """Path -> Platform key of every module served in-process."""
    return {path: key for path, (key, _) in _apps.items()}


def _target(url: str | httpx.URL | None) -> tuple[ASGIApp, str, str] | None:
    """(the module's app, the URL the module sees (its path taken off), the module's key), or None."""
    if not url or _base is None:
        return None
    text = str(url).strip().replace("://localhost", "://127.0.0.1", 1)
    if not text.startswith(_base + "/"):
        return None
    rest = text[len(_base):]
    for path in sorted(_apps, key=len, reverse=True):
        if rest == path or rest.startswith(path + "/") or rest.startswith(path + "?"):
            key, app = _apps[path]
            inner = rest[len(path):]
            if not inner or inner.startswith("?"):
                inner = "/" + inner
            return app, _base + inner, key
    return None


def serves(url: str | None) -> bool:
    """Whether a call to this address stays inside the one backend (no key needed)."""
    return _target(url) is not None


def linked(url: str | None, key: Any) -> bool:
    """A link to another module works with its address and a key, or, in the one backend, its address alone."""
    return bool(url and (key or serves(url)))


def key_header(key: Any, name: str = "X-Bishnoi-Key") -> dict[str, str]:
    """{name: key} when there is a key (a SecretStr or str), else nothing (in-process needs none)."""
    if not key:
        return {}
    value = key.get_secret_value() if hasattr(key, "get_secret_value") else str(key)
    return {name: value} if value else {}


def caller(request: Any) -> str | None:
    """The module that made this request in-process (its Platform key), or None (from outside)."""
    scope = getattr(request, "scope", None)
    value = scope.get(MARK) if isinstance(scope, dict) else None
    return value if isinstance(value, str) and value else None


# --- running a request against a module's app ----------------------------------------------------


def _run(app: ASGIApp, req: httpx.Request, who: str) -> httpx.Response:
    url = req.url
    body = req.read()
    host = url.host
    port = url.port or {"http": 80, "https": 443}.get(url.scheme, 80)
    headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in req.headers.multi_items()]
    if not any(k == b"host" for k, _ in headers):
        headers.insert(0, (b"host", url.netloc))
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": req.method,
        "scheme": url.scheme,
        "path": url.path,
        "raw_path": url.raw_path.split(b"?", 1)[0],
        "root_path": "",
        "query_string": url.query,
        "headers": headers,
        "client": ("127.0.0.1", 0),
        "server": (host, port),
        "extensions": {},
        "state": {},
        MARK: who,
    }
    status: list[int] = []
    out_headers: list[tuple[str, str]] = []
    chunks: list[bytes] = []

    async def call() -> None:
        done = anyio.Event()
        sent = False

        async def receive() -> dict:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            await done.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict) -> None:
            if message["type"] == "http.response.start":
                status.append(message["status"])
                out_headers.extend((k.decode("latin-1"), v.decode("latin-1")) for k, v in message.get("headers", []))
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    done.set()

        try:
            await app(scope, receive, send)
        finally:
            done.set()

    try:
        # Its own event loop, in its own thread: safe from a route (sync or async) and from a
        # background thread alike, and never waits on the loop serving the caller.
        with anyio.from_thread.start_blocking_portal() as portal:
            portal.call(call)
    except Exception:  # noqa: BLE001 (as a server would: the caller gets a 500, the log the error)
        log.exception("In-process call from %s to %s failed.", who, url)
        if not status:
            status.append(500)
            out_headers.clear()
            chunks.clear()
    if not status:
        status.append(500)
    if req.method == "HEAD":
        chunks.clear()
    return httpx.Response(status[0], headers=out_headers, content=b"".join(chunks), request=req)


_HTTPX_KWARGS = ("params", "headers", "json", "content", "data", "files", "cookies")


def request(who: str, method: str, url: str, **kwargs: Any) -> httpx.Response:
    """httpx.request(method, url, **kwargs), in-process when the address is a module of the one backend."""
    found = _target(url)
    if found is None:
        return httpx.request(method, url, **kwargs)
    app, inner, _ = found
    build = {k: kwargs[k] for k in _HTTPX_KWARGS if k in kwargs and kwargs[k] is not None}
    cookies = build.pop("cookies", None)
    req = httpx.Request(method.upper(), inner, **build)
    if cookies:
        httpx.Cookies(cookies).set_cookie_header(req)
    return _run(app, req, who)


def _verb(name: str) -> Callable[..., httpx.Response]:
    def call(who: str, url: str, **kwargs: Any) -> httpx.Response:
        if _target(url) is None:
            return getattr(httpx, name)(url, **kwargs)
        return request(who, name.upper(), url, **kwargs)

    call.__name__ = name
    call.__doc__ = f"httpx.{name}(url, **kwargs), in-process when the address is a module of the one backend."
    return call


get = _verb("get")
post = _verb("post")
put = _verb("put")
patch = _verb("patch")
delete = _verb("delete")


class _UrlResponse:
    """What urllib.request.urlopen gives, for the callers that use it."""

    def __init__(self, response: httpx.Response, url: str):
        self._response = response
        self._body = io.BytesIO(response.content)
        self.status = self.code = response.status_code
        self.reason = response.reason_phrase
        self.url = url
        self.headers = self.msg = _message(response)

    def read(self, amount: int = -1) -> bytes:
        return self._body.read(amount)

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self.url

    def info(self) -> http.client.HTTPMessage:
        return self.headers

    def close(self) -> None:
        self._body.close()

    def __enter__(self) -> _UrlResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _message(response: httpx.Response) -> http.client.HTTPMessage:
    message = http.client.HTTPMessage()
    for k, v in response.headers.multi_items():
        message[k] = v
    return message


def urlopen(who: str, req: urllib.request.Request | str, data: bytes | None = None, timeout: float | None = None, **kwargs: Any):
    """urllib.request.urlopen(req, ...), in-process when the address is a module of the one backend.
    As urllib does: an answer of 400 or more raises urllib.error.HTTPError (its body readable)."""
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    if _target(url) is None:
        # Passed on as the caller gave them (tests stand in for urlopen with the same arguments).
        if data is not None:
            kwargs["data"] = data
        if timeout is not None:
            kwargs["timeout"] = timeout
        return urllib.request.urlopen(req, **kwargs)
    if isinstance(req, urllib.request.Request):
        method = req.get_method()
        headers = dict(req.header_items())
        body = req.data if data is None else data
    else:
        method = "POST" if data is not None else "GET"
        headers, body = {}, data
    response = request(who, method, url, headers=headers, content=body)
    if response.status_code >= 400:
        raise urllib.error.HTTPError(url, response.status_code, response.reason_phrase, _message(response), io.BytesIO(response.content))
    return _UrlResponse(response, url)
