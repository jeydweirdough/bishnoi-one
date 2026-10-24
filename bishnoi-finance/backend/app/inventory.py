"""Bishnoi One Inventory, as Finance uses it: its suppliers, and what they delivered.

Suppliers stay in Inventory, one list (decided 2026-10-24). A bill is made out
to one of them; what the bill needs (name, TIN, address, VAT registration) is
copied onto it when it's made, so a posted bill still reads the same after the
supplier's record changes. A bill can start from a delivery received there.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from app.config import Settings

TIMEOUT = 10  # seconds

# The company of the latest Bishnoi One sign-in here (app/routers/auth.py): Inventory keeps a database
# per company, so each call names it. COMPANY in the settings, when set, comes first.
last_company: str | None = None


class InventoryUnavailable(Exception):
    """Inventory didn't answer, or refused: the message says which, for people."""


def _get(settings: Settings, path: str, *, missing: str = "Inventory has no such record.") -> dict:
    if not settings.inventory_linked:
        raise InventoryUnavailable("Finance is not connected to Inventory, where the suppliers are. Please contact your system administrator.")
    headers = {"X-Bishnoi-Key": settings.inventory_api_key.get_secret_value(), "Accept": "application/json"}
    if company := (settings.company or last_company):
        headers["X-Bishnoi-Company"] = company
    request = urllib.request.Request(f"{settings.inventory_api_url}{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise InventoryUnavailable("The Inventory connection could not be authenticated. Please contact your system administrator.") from e
        if e.code == 404:
            raise InventoryUnavailable(missing) from e
        raise InventoryUnavailable(f"Inventory answered with an error ({e.code}). Try again in a minute.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise InventoryUnavailable("Inventory can't be reached just now. Try again in a minute.") from e


def find_suppliers(settings: Settings, q: str | None = None) -> list[dict]:
    query = f"?{urllib.parse.urlencode({'q': q})}" if q else ""
    return _get(settings, f"/integration/suppliers{query}")["items"]


def read_supplier(settings: Settings, supplier_id: str) -> dict:
    return _get(settings, f"/integration/suppliers/{urllib.parse.quote(supplier_id)}", missing="Inventory has no such supplier.")


def supplier_deliveries(settings: Settings, supplier_id: str) -> list[dict]:
    return _get(settings, f"/integration/suppliers/{urllib.parse.quote(supplier_id)}/receipts", missing="Inventory has no such supplier.")["items"]
