"""Marketing requests, and the part Bishnoi One Finance plays in them.

A request is the CRM's until its Team Lead approves it: then it's sent to
Finance, which releases the money and checks how it was spent. From then on
Finance's copy is the one that counts; the CRM keeps the last answer
(`finance`) and its status mirrors Finance's, asked for again when someone
looks (nothing runs in the background on Vercel), as stock is from Inventory.

The requester sends their receipts through the CRM: each one goes straight to
Finance, which keeps it.

Finance is asked with the key it gave the CRM (FINANCE_API_URL,
FINANCE_API_KEY), the same one tax uses.
"""

import base64
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import FundRequest

log = logging.getLogger(__name__)

TIMEOUT = 15  # seconds
# How long Finance's last answer stands before it's asked again.
FRESH_FOR = timedelta(seconds=30)
# Finance's steps; once a request is at one of these, Finance has it.
FINANCE_STATUSES = ("to_release", "to_liquidate", "to_check", "to_return", "to_reimburse", "closed", "cancelled")
# Nothing more happens to these, here or in Finance.
FINISHED = ("declined", "cancelled", "closed")


class FinanceUnavailable(Exception):
    """Finance didn't answer, or refused: the message says which, for people."""


class FinanceRefused(Exception):
    """Finance answered, and said no (a step that's no longer possible): its words."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


def call(settings: Settings, method: str, path: str, body: dict | None = None, params: dict | None = None, raw: bool = False):
    """One call to Finance's /integration/funds. Returns the JSON answer, or
    (bytes, content type) when `raw`."""
    if not settings.finance_linked:
        raise FinanceUnavailable("The CRM isn't linked to Finance yet (FINANCE_API_URL, FINANCE_API_KEY), so the money can't be released.")
    url = f"{settings.finance_api_url}/integration/funds/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"X-Bishnoi-Key": settings.finance_api_key.get_secret_value(), "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 (the address is ours, from settings)
            content = response.read()
            if raw:
                return content, response.headers.get("Content-Type", "application/octet-stream")
            return json.loads(content)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise FinanceUnavailable("Finance refused the CRM's key: check FINANCE_API_KEY here and INTEGRATION_KEYS there.") from e
        if 300 <= e.code < 400:
            # A redirect: the address is a website (Finance's screens), not its API.
            raise FinanceUnavailable("FINANCE_API_URL isn't Finance's API: use the API's own address (locally, http://127.0.0.1:8303).") from e
        detail = ""
        try:
            detail = json.loads(e.read()).get("detail", "")
        except (ValueError, AttributeError):
            pass
        if isinstance(detail, list):  # a field error: its message
            detail = "; ".join(d.get("msg", "") for d in detail if isinstance(d, dict))
        if e.code in (404, 409, 422) and detail:
            raise FinanceRefused(str(detail), e.code) from e
        raise FinanceUnavailable(f"Finance answered with an error ({e.code}).") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise FinanceUnavailable("Finance can't be reached right now.") from e


# --- keeping the CRM's copy -------------------------------------------------------------------


def take(r: FundRequest, answer: dict) -> None:
    """Finance's answer about a request, kept, and its status mirrored."""
    r.finance = answer
    r.finance_synced_at = datetime.now(UTC)
    r.finance_error = None
    if answer.get("status") in FINANCE_STATUSES:
        r.status = answer["status"]


def send(settings: Settings, r: FundRequest) -> bool:
    """An approved request, to Finance. False (the reason kept) if Finance
    can't take it now: it's tried again the next time anyone looks."""
    body = {
        "sourceId": r.id,
        "number": r.number,
        "requesterName": r.owner.full_name,
        "requesterEmail": r.owner.email,
        "teamName": r.owner.team.name if r.owner.team else None,
        "purpose": r.purpose_name,
        "details": r.details,
        "customerName": r.company.name if r.company else None,
        "neededOn": r.needed_on,
        "liquidate": r.liquidate,
        "requestedCentavos": r.amount_centavos,
        "approvedCentavos": r.approved_centavos,
        "approvedByName": r.decided_by.full_name if r.decided_by else "",
        "approvedAt": (r.decided_at or datetime.now(UTC)).isoformat(),
        "approvalNote": r.decision_note,
    }
    try:
        take(r, call(settings, "POST", "requests", body))
        return True
    except (FinanceUnavailable, FinanceRefused) as e:
        log.warning("Marketing request %s not sent to Finance: %s", r.number, e)
        r.finance_error = str(e)[:300]
        return False


def refresh(db: Session, settings: Settings, requests: list[FundRequest], fresh: bool = False) -> str | None:
    """Brings these requests up to date with Finance: sends the approved ones
    it doesn't have yet, and asks where the rest are (a list only for those
    not asked in FRESH_FOR; one request, `fresh`, always). Returns why it
    couldn't, if it couldn't; the page shows the last answer either way."""
    if not settings.finance_linked:
        return None
    now = datetime.now(UTC)
    changed = False
    for r in requests:
        if r.status == "approved":
            send(settings, r)
            changed = True
    stale = [
        r for r in requests
        if r.status in FINANCE_STATUSES and r.status not in FINISHED
        and (fresh or r.finance_synced_at is None or now - as_utc(r.finance_synced_at) > FRESH_FOR)
    ]
    problem = None
    if stale:
        try:
            answers = call(settings, "GET", "requests", params={"ids": ",".join(r.id for r in stale)})["items"]
            for r in stale:
                if r.id in answers:
                    take(r, answers[r.id])
            changed = True
        except (FinanceUnavailable, FinanceRefused) as e:
            problem = str(e)
    if changed:
        db.commit()
    return problem


def as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment


# --- what spending is sorted into -------------------------------------------------------------

_categories: tuple[float, list[dict]] | None = None


def categories(settings: Settings) -> list[dict]:
    """Finance's expense categories, kept for five minutes."""
    global _categories
    if _categories and time.monotonic() - _categories[0] < 300:
        return _categories[1]
    items = call(settings, "GET", "categories")["items"]
    _categories = (time.monotonic(), items)
    return items


def receipt_body(name: str, content_type: str, data: bytes) -> dict:
    return {"name": name[:160], "contentType": content_type, "data": base64.b64encode(data).decode()}
