"""Where each application's API is, now that every module is part of one backend (2026-11-17).

Each module answers at BACKEND_URL + its path (/crm, /inventory, ...; backend/main.py), so the
Platform works the address out instead of reading the one registered for it in Applications
(nbpl_applications.api_url, from when every app was its own server). With BACKEND_URL unset
(this module's tests, a Platform run alone), the registered address is used as before.

Everything that calls an application (connect keys, links, roles, the company and org-chart
passes, events, /public/applications, health checks) asks here: `api_url(app)`.
"""

from __future__ import annotations

from modules.platform.models import Application

# Each application's key on the Platform -> its path in the one backend.
PATHS: dict[str, str] = {
    "platform": "/platform",
    "crm": "/crm",
    "inventory": "/inventory",
    "finance": "/finance",
    "exec": "/admin",
    "admin": "/admin",
    "pharmacy": "/pharmacy",
    "inlicensing": "/in-licensing",
    "in-licensing": "/in-licensing",
    "regulatory": "/regulatory",
}

_backend: str | None = None


def configure(backend_url: str | None) -> None:
    """Set by create_app from the settings' BACKEND_URL (None: registered addresses)."""
    global _backend
    _backend = backend_url.strip().rstrip("/") if backend_url else None


def backend() -> str | None:
    return _backend


def in_backend(app: Application) -> bool:
    """Whether the application is a module of the one backend (its address is worked out)."""
    return _backend is not None and app.key in PATHS


def api_url(app: Application) -> str | None:
    """The application's API address, no / at the end; None when it has none."""
    if in_backend(app):
        return _backend + PATHS[app.key]
    return app.api_url.rstrip("/") if app.api_url else None


def health_url(app: Application) -> str | None:
    """Where the Platform asks whether it's up."""
    if in_backend(app):
        return _backend + PATHS[app.key] + "/health"
    return app.health_url
