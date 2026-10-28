"""Bishnoi One Inventory, as Finance uses it: what each product costs, so an invoice books its cost
of goods sold (decided 2026-10-28, feature plan step 3). Read with the key Inventory gave Finance,
at Finance's company (CRM_COMPANY). Nothing breaks without it: the invoice is issued with no cost.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from app.config import Settings

TIMEOUT = 10  # seconds


def unit_costs(settings: Settings, skus: list[str]) -> dict[str, int] | None:
    """Each known SKU's cost per unit, in centavos (keys upper-cased); None when Inventory can't be asked."""
    wanted = sorted({s.strip() for s in skus if s and s.strip()})
    if not wanted or not settings.inventory_linked:
        return None if not settings.inventory_linked else {}
    headers = {"X-Bishnoi-Key": settings.inventory_api_key.get_secret_value(), "Accept": "application/json"}
    if settings.crm_company:
        headers["X-Bishnoi-Company"] = settings.crm_company
    url = f"{settings.inventory_api_url}/integration/costs?{urllib.parse.urlencode({'skus': ','.join(wanted)})}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT) as response:
            items = json.loads(response.read()).get("items", {})
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    return {sku.upper(): int(v.get("unitCost") or 0) for sku, v in items.items()}
