"""Every page Finance reads, on SQLite and (with FINANCE_TEST_POSTGRES_ADMIN_URL) on a
throwaway PostgreSQL database: none may fail with a server error.

Official Finance runs on PostgreSQL (Neon) while the other tests run on SQLite, which
accepts SQL that PostgreSQL refuses. On 2026-10-29 the bills list failed on Neon
("nbfi_bills.status must appear in the GROUP BY clause"): it grouped by a CASE whose
values were sent as separate placeholders in SELECT and GROUP BY.
"""

from .test_concurrent_saves import app  # noqa: F401 (the SQLite / PostgreSQL fixture)
from .test_invoices import issued, ready
from .test_tax_api import ana, client  # noqa: F401 (fixtures)
from .test_vouchers import prepare, ready_bill, team  # noqa: F401 (fixtures)


ZOHO_LISTS = {"/finance/zoho-invoices", "/finance/zoho-sales-orders"}


def plain_reads(app):  # noqa: F811
    """GET endpoints with no path parameters (lists, dashboards, reports, settings), from the
    app's API description: `app.routes` nests included routers in this FastAPI version, so a
    flat walk of it finds almost nothing. Endpoints hidden from the API docs aren't covered."""
    paths = sorted(p for p, methods in app.openapi()["paths"].items() if "get" in methods and "{" not in p)
    assert "/finance/bills" in paths and len(paths) > 40, paths  # the sweep must really reach the pages
    return paths


def test_no_page_fails_on_either_database(client, ana, team, app):  # noqa: F811
    # Something in the main lists, so the queries have rows to group and join.
    ready(client, ana)
    issued(client, ana)
    s, b = ready_bill(client, team)
    prepare(client, team["aubrey"], s, [{"billId": b["id"], "amountCentavos": 100_000}])
    failed = {}
    for path in plain_reads(app):
        r = client.get(path, headers=ana)
        # The Zoho lists refuse plainly where no Zoho connection is set up, as in these tests.
        if path in ZOHO_LISTS and r.status_code == 503 and "Zoho" in r.json()["detail"]:
            continue
        if r.status_code >= 500:
            failed[path] = (r.status_code, r.text[:200])
    assert not failed, failed


def test_the_bills_list_counts_each_state(client, ana, team, app):  # noqa: F811
    s, b = ready_bill(client, team)
    r = client.get("/finance/bills", headers=ana)
    assert r.status_code == 200, r.text
    assert r.json()["counts"]["ready"] == 1
