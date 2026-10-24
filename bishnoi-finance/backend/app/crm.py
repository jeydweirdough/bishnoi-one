"""Bishnoi One CRM, as Finance uses it: its customers, and its prices.

Customers: who an invoice is made out to. The CRM keeps them; Finance reads
them with the key the CRM gave it (its INTEGRATION_KEYS), the same way the CRM
reads Inventory's products. What the invoice needs is copied onto it when it's
made, so an issued invoice still reads the same after the customer's record
changes.

Prices: every product's price is Finance's. A manager's price, and a quote at
a price a rep asked for, wait in the CRM until Finance approves them here
(app/routers/prices.py); the decision is the CRM's to keep.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from app.config import Settings

TIMEOUT = 10  # seconds


class CrmUnavailable(Exception):
    """The CRM didn't answer, or refused: the message says which, for people."""


def _call(settings: Settings, path: str, body: dict | None = None, *, missing: str = "The CRM has no such record.") -> dict:
    """GET path, or POST body to it, on the CRM's integration API."""
    if not settings.crm_linked:
        raise CrmUnavailable("Finance is not connected to the CRM. Please contact your system administrator.")
    headers = {"X-Bishnoi-Key": settings.crm_api_key.get_secret_value(), "Accept": "application/json"}
    # The CRM keeps one database per company, so each call names Finance's
    # (CRM_COMPANY). In production the CRM won't guess, so don't ask unnamed.
    if settings.crm_company:
        headers["X-Bishnoi-Company"] = settings.crm_company
    elif settings.is_production:
        raise CrmUnavailable("Finance is not connected to a CRM company (CRM_COMPANY isn't set). Please contact your system administrator.")
    data = None
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    request = urllib.request.Request(f"{settings.crm_api_url}{path}", data=data, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise CrmUnavailable("CRM connection could not be authenticated. Please contact your system administrator.") from e
        if e.code == 404:
            raise CrmUnavailable(missing) from e
        if e.code in (409, 422):
            # The CRM's own words: already decided, or a reason is needed.
            raise CrmUnavailable(_said(e) or "The CRM didn't take that. Refresh and try again.") from e
        if e.code < 500:
            # Refused for how Finance asked (e.g. no company named): the same
            # request will be refused again, so don't say to try again.
            said = _said(e)
            raise CrmUnavailable(
                f"The CRM refused the request ({e.code}{': ' + said if said else ''}). Trying again won't help. Please contact your system administrator."
            ) from e
        raise CrmUnavailable(f"The CRM answered with an error ({e.code}). Try again in a minute.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise CrmUnavailable("The CRM can't be reached just now. Try again in a minute.") from e


def _said(e: urllib.error.HTTPError) -> str | None:
    """What the CRM said was wrong, when it said it in words."""
    try:
        detail = json.loads(e.read()).get("detail")
    except (ValueError, OSError):
        return None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        return detail[0].get("msg")
    return None


def _get(settings: Settings, path: str) -> dict:
    try:
        return _call(settings, f"/integration/customers{path}", missing="The CRM has no such customer.")
    except CrmUnavailable as e:
        if "not connected" in str(e) or "can't be reached" in str(e) or "refused the request" in str(e):
            raise CrmUnavailable(f"{e} Or type the customer's details instead.") from None
        raise


def find_customers(settings: Settings, q: str | None) -> list[dict]:
    query = f"?{urllib.parse.urlencode({'q': q})}" if q else ""
    return _get(settings, query)["items"]


def read_customer(settings: Settings, customer_id: str) -> dict:
    return _get(settings, f"/{urllib.parse.quote(customer_id, safe='')}")


# --- prices ------------------------------------------------------------------------------------


def waiting_prices(settings: Settings) -> dict:
    """{prices, quotes, total}: managers' prices and quotes at requested prices, waiting for Finance."""
    return _call(settings, "/integration/prices")


def decide_price(settings: Settings, decision: dict) -> dict:
    """decision: {kind, productId, priceTypeCode, teamId, decision, reason, byName}."""
    return _call(settings, "/integration/prices/decide", decision, missing="That price isn't waiting any more: someone has decided it.")


def decide_quote(settings: Settings, quote_id: str, decision: dict) -> dict:
    """decision: {decision, note, byName}."""
    return _call(settings, f"/integration/prices/quotes/{urllib.parse.quote(quote_id, safe='')}/decide", decision, missing="The CRM has no such quote.")
