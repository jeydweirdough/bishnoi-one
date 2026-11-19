"""The one backend's front door (backend/main.py's `app`): /<module>/... goes to that module with
its path prefix taken off, so the module sees the paths it had when it ran alone; anything else
goes to the backend's own routes (GET /health).

A request from outside never carries the in-process mark (modules/inprocess.py MARK): it's taken
out of every scope that comes through here, so only a module calling another in-process is
trusted as that module.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from fastapi import FastAPI

from modules import inprocess

Scope = MutableMapping[str, Any]
ASGIApp = Callable[[Scope, Callable, Callable], Awaitable[None]]


class Modules:
    """Sends /<module>/... to that module with the prefix taken off; everything else to `root`.

    The module sees the path it had when it ran alone. Its interactive docs (/crm/docs) get
    root_path so they load /crm/openapi.json and try requests under /crm."""

    def __init__(self, root_app: ASGIApp, mounts: list[tuple[str, FastAPI]]):
        self.root = root_app
        self.mounts = sorted(mounts, key=lambda m: len(m[0]), reverse=True)

    async def __call__(self, scope: Scope, receive: Callable, send: Callable) -> None:
        if scope["type"] in ("http", "websocket"):
            # Only modules/inprocess.py marks a request as another module's: never one from outside.
            if inprocess.MARK in scope:
                scope = {k: v for k, v in scope.items() if k != inprocess.MARK}
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
