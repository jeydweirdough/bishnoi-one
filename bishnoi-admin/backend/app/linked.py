"""Calls to the other Bishnoi One apps a promotional material goes through.

    Pharmacy  the pharmacist approves each design
        POST {PHARMACY_API_URL}/integration/materials              a version, sent or sent again
        GET  {PHARMACY_API_URL}/integration/materials/{version}    the pharmacist's answer
    CRM       the team's manager approves giving some out
        GET  {CRM_API_URL}/integration/teams                       teams, their manager and people
        POST {CRM_API_URL}/integration/material-requests           a distribution, sent or updated
        GET  {CRM_API_URL}/integration/material-requests/{id}      the manager's answer
    X-Bishnoi-Key: the key the platform's Connections page gives for that link

Admin keeps each app's last answer and asks again when someone opens the
material (nothing runs in the background on Vercel).
"""

import logging

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

TIMEOUT = 15  # seconds
NAMES = {"pharmacy": "Pharmacy", "crm": "the CRM"}


class Unavailable(Exception):
    """The other app didn't answer, or refused the key: the message says which, for people."""


class Refused(Exception):
    """The other app answered, and said no: its words."""


def linked(settings: Settings, app: str) -> bool:
    return bool(getattr(settings, f"{app}_api_url") and getattr(settings, f"{app}_api_key"))


def call(settings: Settings, app: str, method: str, path: str, body: dict | None = None) -> dict:
    """One call to Pharmacy or the CRM. Returns its JSON answer."""
    name = NAMES[app]
    if not linked(settings, app):
        raise Unavailable(f"Admin is not connected to {name} yet. Please contact your system administrator.")
    headers = {"X-Bishnoi-Key": getattr(settings, f"{app}_api_key").get_secret_value(), "Accept": "application/json"}
    if settings.company:
        headers["X-Bishnoi-Company"] = settings.company
    url = getattr(settings, f"{app}_api_url").rstrip("/") + path
    try:
        r = httpx.request(method, url, json=body, headers=headers, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise Unavailable(f"{name[0].upper()}{name[1:]} can't be reached right now.") from e
    if r.status_code == 401:
        raise Unavailable(f"The connection to {name} could not be verified. Please contact your system administrator.")
    if r.status_code >= 400:
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except (ValueError, AttributeError):
            pass
        if isinstance(detail, list):  # a field error: its message
            detail = "; ".join(d.get("msg", "") for d in detail if isinstance(d, dict))
        if r.status_code in (404, 409, 422) and detail:
            raise Refused(str(detail))
        raise Unavailable(f"{name[0].upper()}{name[1:]} answered with an error ({r.status_code}).")
    try:
        return r.json()
    except ValueError as e:
        raise Unavailable(f"{name[0].upper()}{name[1:]}'s answer couldn't be read.") from e
