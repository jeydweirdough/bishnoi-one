"""Customers, from Nabhi CRM: who an invoice is made out to.

The CRM keeps the customers; Finance reads them with the key the CRM gave it
(its INTEGRATION_KEYS), the same way the CRM reads Inventory's products. What
the invoice needs is copied onto it when it's made, so an issued invoice
still reads the same after the customer's record changes.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from app.config import Settings

TIMEOUT = 10  # seconds


class CrmUnavailable(Exception):
    """The CRM didn't answer, or refused: the message says which, for people."""


def _get(settings: Settings, path: str) -> dict:
    if not settings.crm_linked:
        raise CrmUnavailable("Finance isn't linked to the CRM (CRM_API_URL, CRM_API_KEY): type the customer's details instead.")
    request = urllib.request.Request(
        f"{settings.crm_api_url}/integration/customers{path}",
        headers={"X-Nabhi-Key": settings.crm_api_key.get_secret_value(), "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise CrmUnavailable("The CRM refused Finance's key: check CRM_API_KEY here and INTEGRATION_KEYS there.") from e
        if e.code == 404:
            raise CrmUnavailable("The CRM has no such customer.") from e
        raise CrmUnavailable(f"The CRM answered with an error ({e.code}). Try again in a minute.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise CrmUnavailable("The CRM can't be reached just now. Try again in a minute, or type the customer's details.") from e


def find_customers(settings: Settings, q: str | None) -> list[dict]:
    query = f"?{urllib.parse.urlencode({'q': q})}" if q else ""
    return _get(settings, query)["items"]


def read_customer(settings: Settings, customer_id: str) -> dict:
    return _get(settings, f"/{urllib.parse.quote(customer_id, safe='')}")
