"""Bishnoi One's one backend: every module's API in one process.

    uv run main.py                      # development, reloading on code changes (port 8300)
    uv run main.py --port 8399
    uv run uvicorn main:app --port 8300 # as a server runs it (Coolify)

Each module is its former API, unchanged: its own create_app() with its own middleware,
errors, sessions, permissions, database and Alembic history. It answers under its path:

    /platform  /crm  /inventory  /finance  /admin  /pharmacy  /in-licensing  /regulatory

so /crm/customers here is what /customers was on the CRM's own API. GET /health is the
backend's own (which modules started).

One address: BACKEND_URL (default http://127.0.0.1:8300; on the server the backend's internal
address). A module's address is BACKEND_URL + its path, for the other modules (PLATFORM_API_URL,
INVENTORY_API_URL... default to it, modules/module_settings.py link_defaults) and for the
Platform's Applications (modules/platform/addresses.py).

How the modules start: a module's create_app() brings its database up to date (migrations)
and starts its background work when it is called, not in a startup event, so this file calls
them in order when it is imported: Platform first (the others ask it for passes and keys),
Finance last. One that can't start (a setting, its database) answers every request under its
path with 503 saying which setting to check (its server.py, as each API did on its own) and
the others start regardless. Any startup/shutdown events a module has (none today) run too:
the backend's lifespan enters each module's own lifespan, in the same order.

Why not Starlette's Mount: a mounted app sees its prefix in request.url.path, and the modules
compare paths ("/auth/login", "/graphql"); Inventory's own routes also start with /inventory.
So the prefix is taken off the path before the module sees it, exactly as when it ran alone.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import logging
from collections.abc import Awaitable, Callable, MutableMapping
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from modules.module_settings import link_defaults

log = logging.getLogger("bishnoi.backend")

BACKEND_DIR = Path(__file__).resolve().parent

# (package, path), in the order they start.
MODULES: list[tuple[str, str]] = [
    ("platform", "/platform"),
    ("crm", "/crm"),
    ("inventory", "/inventory"),
    ("admin", "/admin"),
    ("pharmacy", "/pharmacy"),
    ("in_licensing", "/in-licensing"),
    ("regulatory", "/regulatory"),
    ("finance", "/finance"),
]

Scope = MutableMapping[str, Any]
ASGIApp = Callable[[Scope, Callable, Callable], Awaitable[None]]


def _unavailable(name: str, error: BaseException) -> FastAPI:
    """What a module answers when it can't even be imported or built: 503, the error's kind, never its text."""
    fallback = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    body = {"ok": False, "app": name, "problem": "startup", "check": ["the host's logs"],
            "hint": "The full error is in the logs.", "error": f"{type(error).__module__}.{type(error).__name__}"}

    @fallback.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def unavailable(request: Request, path: str) -> JSONResponse:
        return JSONResponse(body, status_code=503)

    return fallback


def _start(name: str) -> tuple[FastAPI, bool]:
    """A module's app, started. Its server.py when it has one (it answers 503 by itself when it
    can't start, and waits for a database that's coming up); else its create_app()."""
    try:
        if importlib.util.find_spec(f"modules.{name}.server") is not None:
            module_app = importlib.import_module(f"modules.{name}.server").app
        else:
            module_app = importlib.import_module(f"modules.{name}.main").create_app()
    except Exception as error:  # noqa: BLE001 (one module must not stop the others)
        log.exception("Module %s could not start", name)
        return _unavailable(name, error), False
    # server.py's own fallback has no settings: that's how a module that didn't start is told apart.
    started = getattr(module_app.state, "settings", None) is not None
    if not started:
        log.error("Module %s did not start; it answers 503 until it can.", name)
    return module_app, started


def _serve() -> None:
    """`uv run main.py`: development, reloading on code changes. Only the server process uvicorn
    starts (main:app) starts the modules; this one just watches the files."""
    import uvicorn

    parser = argparse.ArgumentParser(description="Run Bishnoi One's backend with auto-reload.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8300)
    args = parser.parse_args()
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=True,
        # A reload doesn't wait on connections the screens keep open (they never close on
        # their own, so it waited for ever and served the old code).
        timeout_graceful_shutdown=2,
        reload_dirs=[str(BACKEND_DIR / "modules")],
        reload_includes=["*.py"],
    )


if __name__ == "__main__":
    _serve()
    raise SystemExit(0)


# Where every module is: BACKEND_URL + its path (modules/module_settings.py). Set before any
# module reads its settings, so PLATFORM_API_URL, INVENTORY_API_URL... need no setting of their own.
BACKEND_URL = link_defaults(BACKEND_DIR / ".env")

APPS: dict[str, FastAPI] = {}
STARTED: dict[str, bool] = {}
for _name, _path in MODULES:
    APPS[_name], STARTED[_name] = _start(_name)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with AsyncExitStack() as stack:
        for name, _ in MODULES:
            module_app = APPS[name]
            try:
                await stack.enter_async_context(module_app.router.lifespan_context(module_app))
            except Exception:  # noqa: BLE001
                log.exception("Module %s's startup failed", name)
        yield


root = FastAPI(title="Bishnoi One", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@root.get("/health", tags=["health"])
def health() -> dict:
    return {"ok": True, "app": "bishnoi-one", "modules": {path.strip("/"): STARTED[name] for name, path in MODULES}}


class Modules:
    """Sends /<module>/... to that module with the prefix taken off; everything else to `root`.

    The module sees the path it had when it ran alone. Its interactive docs (/crm/docs) get
    root_path so they load /crm/openapi.json and try requests under /crm."""

    def __init__(self, root_app: ASGIApp, mounts: list[tuple[str, FastAPI]]):
        self.root = root_app
        self.mounts = sorted(mounts, key=lambda m: len(m[0]), reverse=True)

    async def __call__(self, scope: Scope, receive: Callable, send: Callable) -> None:
        if scope["type"] in ("http", "websocket"):
            path: str = scope["path"]
            for prefix, module_app in self.mounts:
                if path == prefix or path.startswith(prefix + "/"):
                    child = dict(scope)
                    rest = path[len(prefix):] or "/"
                    child["path"] = rest
                    raw = scope.get("raw_path")
                    if raw is not None:
                        encoded = prefix.encode()
                        child["raw_path"] = (raw[len(encoded):] or b"/") if raw.startswith(encoded) else raw
                    if rest in _docs_paths(module_app):
                        child["root_path"] = scope.get("root_path", "") + prefix
                    await module_app(child, receive, send)
                    return
        await self.root(scope, receive, send)


def _docs_paths(module_app: FastAPI) -> set[str]:
    return {p for p in (module_app.docs_url, module_app.redoc_url, module_app.openapi_url,
                        module_app.swagger_ui_oauth2_redirect_url) if p}


app = Modules(root, [(path, APPS[name]) for name, path in MODULES])
