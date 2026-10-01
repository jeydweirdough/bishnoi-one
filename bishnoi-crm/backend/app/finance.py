"""Tax, from Nabhi Finance: the last step of the price rules.

Finance owns tax for every Nabhi app (benchmarks/decisions.md, D8), so the
CRM doesn't work it out itself: it sends the priced lines, each with its
product's VAT category, and keeps what Finance answers, as the invoice will
show it. Finance is asked with the key it gave the CRM, the same way the CRM
asks Inventory for stock.

A quote isn't saved without its tax while the tax step is on: if Finance
can't be reached, saving waits, rather than a quote going out without it.
"""

import json
import urllib.error
import urllib.request

from app.config import Settings
from app.models import Bundle, Product

TIMEOUT = 10  # seconds


class TaxUnavailable(Exception):
    """Finance didn't answer, or refused: the message says which, for people."""


def _post(settings: Settings, path: str, body: dict) -> dict:
    request = urllib.request.Request(
        f"{settings.finance_api_url}/integration/{path}",
        data=json.dumps(body).encode(),
        headers={"X-Nabhi-Key": settings.finance_api_key.get_secret_value(), "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 (the address is ours, from settings)
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise TaxUnavailable("Finance refused the CRM's key: check FINANCE_API_KEY here and INTEGRATION_KEYS there.") from e
        detail = ""
        try:
            detail = json.loads(e.read()).get("detail", "")
        except (ValueError, AttributeError):
            pass
        raise TaxUnavailable(f"Finance couldn't work out the tax: {detail}" if isinstance(detail, str) and detail else f"Finance answered with an error ({e.code}).") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise TaxUnavailable("Finance can't be reached right now, so the tax can't be worked out.") from e


def tax_parts(line: dict, products: dict[str, Product], bundles: dict[str, Bundle]) -> list[tuple[str, int]]:
    """A priced line as (VAT category, amount) pieces. A bundle sold as one
    line is split across its products by their share of its value, so each is
    taxed by its own category."""
    if line.get("productId"):
        product = products.get(line["productId"])
        return [(product.vat_category if product else "standard", line["totalCentavos"])]
    bundle = bundles.get(line.get("bundleId") or "")
    if bundle is None or not bundle.items:
        return [("standard", line["totalCentavos"])]
    items = [(products.get(i["productId"]), i["qty"]) for i in bundle.items]
    categories = {p.vat_category if p else "standard" for p, _ in items}
    if len(categories) == 1:
        return [(categories.pop(), line["totalCentavos"])]
    # Mixed categories: share the set's price by each item's quantity.
    total, units = line["totalCentavos"], sum(q for _, q in items)
    parts, left = [], total
    for n, (p, qty) in enumerate(items):
        amount = left if n == len(items) - 1 else total * qty // units
        left -= amount
        parts.append((p.vat_category if p else "standard", amount))
    return parts


def add_tax(settings: Settings, priced: dict, products: dict[str, Product], bundles: dict[str, Bundle], prices_include_tax: bool) -> dict:
    """The priced quote, with Finance's tax on each line and its summary.
    Raises TaxUnavailable when Finance can't answer."""
    if not settings.finance_linked:
        raise TaxUnavailable("Tax is switched on in the price rules, but the CRM isn't linked to Finance yet (FINANCE_API_URL, FINANCE_API_KEY).")
    pieces: list[tuple[int, str, int]] = []  # (quote line, category, amount)
    for n, line in enumerate(priced["lines"]):
        for category, amount in tax_parts(line, products, bundles):
            pieces.append((n, category, amount))
    answer = _post(
        settings,
        "tax/compute",
        {
            "pricesIncludeTax": prices_include_tax,
            "lines": [{"quantity": 1, "unitPriceCentavos": amount, "category": category} for _, category, amount in pieces],
        },
    )
    tax_by_line = [0] * len(priced["lines"])
    due_by_line = [0] * len(priced["lines"])
    for (n, _, _), taxed in zip(pieces, answer["lines"], strict=True):
        tax_by_line[n] += taxed["taxCentavos"]
        due_by_line[n] += taxed["totalCentavos"]
    for line, tax, due in zip(priced["lines"], tax_by_line, due_by_line, strict=True):
        line["taxCentavos"], line["amountDueCentavos"] = tax, due
    priced["tax"] = {
        "document": answer["document"],
        "regime": answer["seller"]["regime"],
        "regimeName": answer["seller"]["regimeName"],
        "pricesIncludeTax": answer["pricesIncludeTax"],
        "summary": answer["summary"],
        "notice": answer.get("notice"),
        "totalDueCentavos": answer["totalDueCentavos"],
        "on": answer["on"],
    }
    return priced
