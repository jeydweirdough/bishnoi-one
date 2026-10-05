"""The pharmacist's check on a quote marked Rx, from Bishnoi One Pharmacy.

A quote with prescription medicines is checked by a pharmacist before it's
ordered. The CRM sends it to Pharmacy with the prescription's details; it
lands in the pharmacist's inbox there and is checked as any prescription is
(ten checks, then a verdict). The CRM keeps Pharmacy's last answer and asks
again when someone looks at the quote (nothing runs in the background on
Vercel), the same way marketing requests are followed in Finance.

    POST {PHARMACY_API_URL}/integration/checks          the quote, sent or sent again
    GET  {PHARMACY_API_URL}/integration/checks/{quote}  where the pharmacist is with it
    X-Bishnoi-Key: {PHARMACY_API_KEY}

Pharmacy's verdict ("outcome"): waiting, verified, needs_clarification or
rejected. Only a verified quote can be ordered. One that needs clarification
can be corrected and sent again; a rejected one can't be ordered.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import Settings
from app.tenants import company_header
from app.models import Company, Contact, Quote

log = logging.getLogger(__name__)

TIMEOUT = 15  # seconds
# How long Pharmacy's last answer stands before it's asked again.
FRESH_FOR = timedelta(seconds=30)
# Nothing more happens to these: the pharmacist has decided.
SETTLED = ("verified", "rejected")


class PharmacyUnavailable(Exception):
    """Pharmacy didn't answer, or refused the key: the message says which, for people."""


class PharmacyRefused(Exception):
    """Pharmacy answered, and said no: its words."""


def call(settings: Settings, method: str, path: str, body: dict | None = None) -> dict:
    """One call to Pharmacy's /integration/checks. Returns its JSON answer."""
    if not settings.pharmacy_linked:
        raise PharmacyUnavailable("The CRM isn't linked to Pharmacy yet (PHARMACY_API_URL, PHARMACY_API_KEY), so an Rx quote can't be checked.")
    url = f"{settings.pharmacy_api_url}/integration/checks" + (f"/{urllib.parse.quote(path)}" if path else "")
    headers = {"X-Bishnoi-Key": settings.pharmacy_api_key.get_secret_value(), "Accept": "application/json", **company_header(settings)}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 (the address is ours, from settings)
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise PharmacyUnavailable("Pharmacy refused the CRM's key: check PHARMACY_API_KEY here and INTEGRATION_KEYS there.") from e
        if 300 <= e.code < 400:
            raise PharmacyUnavailable("PHARMACY_API_URL isn't Pharmacy's API: use the API's own address (locally, http://127.0.0.1:8307).") from e
        detail = ""
        try:
            detail = json.loads(e.read()).get("detail", "")
        except (ValueError, AttributeError):
            pass
        if isinstance(detail, list):  # a field error: its message
            detail = "; ".join(d.get("msg", "") for d in detail if isinstance(d, dict))
        if e.code in (404, 409, 422) and detail:
            raise PharmacyRefused(str(detail)) from e
        raise PharmacyUnavailable(f"Pharmacy answered with an error ({e.code}).") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise PharmacyUnavailable("Pharmacy can't be reached right now.") from e


def payload(db: Session, quote: Quote, details: dict) -> dict:
    """The quote as Pharmacy takes it: who it's for, the prescription, the lines."""
    contact = db.get(Contact, quote.contact_id) if quote.contact_id else None
    company = db.get(Company, quote.company_id) if quote.company_id else (contact.company if contact else None)
    return {
        "sourceId": quote.id,
        "reference": quote.number,
        "customer": {
            "name": quote.customer_name,
            "phone": (contact.phone if contact else None) or (company.phone if company else None),
            "email": (contact.email if contact else None) or (company.email if company else None),
            "address": company.address if company else None,
        },
        "prescription": {k: details.get(k) for k in ("prescriberName", "prescriberLicense", "prescriberClinic", "prescribedOn", "notes")},
        "lines": [
            {"code": line.get("productCode"), "name": line.get("productName") or line.get("bundleName") or "Item", "quantity": line.get("quantity") or 1, "unit": line.get("unit")}
            for line in quote.lines
            if (line.get("quantity") or 0) > 0
        ],
        "sentBy": details["sentBy"],
    }


def take(quote: Quote, answer: dict) -> None:
    quote.pharmacy_check = answer
    quote.pharmacy_synced_at = datetime.now(UTC)
    quote.pharmacy_error = None


def send(db: Session, settings: Settings, quote: Quote, details: dict) -> None:
    """Sends (or sends again) the quote for checking. Raises when Pharmacy can't take it."""
    answer = call(settings, "POST", "", payload(db, quote, details))
    quote.pharmacy_sent = details
    take(quote, answer)


def outcome(quote: Quote) -> str | None:
    """waiting, verified, needs_clarification or rejected; None when not sent."""
    return (quote.pharmacy_check or {}).get("outcome") if quote.pharmacy_sent else None


def refresh(settings: Settings, quote: Quote) -> bool:
    """Asks Pharmacy again when its last answer is out of date and not final.
    True when something changed. A failure is kept, not raised: the quote
    still opens, with Pharmacy's last answer and the reason it's not newer."""
    if not quote.pharmacy_sent or outcome(quote) in SETTLED or not settings.pharmacy_linked:
        return False
    synced = quote.pharmacy_synced_at
    if synced is not None:
        synced = synced.replace(tzinfo=UTC) if synced.tzinfo is None else synced
        if datetime.now(UTC) - synced < FRESH_FOR:
            return False
    try:
        take(quote, call(settings, "GET", quote.id))
    except (PharmacyUnavailable, PharmacyRefused) as e:
        log.warning("Pharmacy check for %s not refreshed: %s", quote.number, e)
        quote.pharmacy_error = str(e)[:300]
    return True
