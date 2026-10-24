"""BIR files (2026-10-22): the Sales DAT screen is only for a role given "Prepare
BIR files", which no role has until it's ticked (Sir Rommel's, for now)."""

from app.permissions import ALL_PERMISSIONS, STARTING_ROLES

from .test_dashboard import BIR, HEAD, person
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)


def test_no_starting_role_but_the_administrator_prepares_bir_files():
    assert "bir.prepare" in ALL_PERMISSIONS
    holders = [name for _, name, _, perms in STARTING_ROLES if "bir.prepare" in perms]
    assert holders == ["Administrator"]


def test_only_a_role_with_the_permission_opens_the_sales_dat(client, ana, ben):
    rommel = person(client, ana, "BIR and Compliance", BIR + ["bir.prepare"])
    malou = person(client, ana, "Finance Head", HEAD)
    assert client.get("/finance/bir/sales-dat", headers=ben).status_code == 403
    assert client.get("/finance/bir/sales-dat", headers=malou).status_code == 403
    got = client.get("/finance/bir/sales-dat", headers=rommel)
    assert got.status_code == 200
    companies = {c["tin"]: c for c in got.json()["companies"]}
    # 2MG as filed so far, not yet confirmed; GPI known by its TIN, its RDO and year-end not yet.
    assert companies["010065182"] == {**companies["010065182"], "rdo": "53A", "yearEndMonth": 12, "confirmed": False}
    assert companies["605059166"]["rdo"] is None and companies["605059166"]["yearEndMonth"] is None
    assert client.get("/finance/bir/sales-dat", headers=ana).status_code == 200  # the Administrator holds every permission
