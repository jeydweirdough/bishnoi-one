"""Fictional regressions for consignment supplier origin and optional brokerage tax."""
import pytest

from app.consignment_bills import vendor_for
from app.models import Supplier
from app.payables import withholding_out
from .test_tax_api import app, ana, client  # noqa: F401


@pytest.mark.parametrize("name,origin", [("TEST Local Supply", "local"), ("TEST Export Limited", "foreign")])
def test_new_consignment_suppliers_have_an_origin(app, name, origin):
    with app.state.sessions() as db:
        row = vendor_for(db, {"number": "TEST-CS-1", "supplier": {"name": name}})
        assert row.origin == origin


@pytest.mark.parametrize("by_tin", [False, True])
def test_consignment_keeps_a_persons_existing_origin(app, by_tin):
    with app.state.sessions() as db:
        existing = Supplier(name="TEST Local Branch Limited", origin="local", tin="123-456-789", created_by="TEST")
        db.add(existing)
        db.flush()
        incoming = {"name": "TEST Different Name", "tin": "123456789"} if by_tin else {"name": existing.name}
        found = vendor_for(db, {"number": "TEST-CS-2", "supplier": incoming})
        assert found.id == existing.id and found.origin == "local"


def test_wc140_is_selectable_and_calculates_only_when_chosen():
    option = next((x for x in withholding_out() if x["code"] == "WC140"), None)
    assert option is not None and option["rateBp"] == 1500
    assert "720,000" in option["name"]
    assert not any(x["code"] == "WC640" for x in withholding_out())


def test_brokerage_does_not_default_on_importations(app, client, ana):
    from .test_payables import account, supplier, bill
    broker = supplier(client, ana, name="TEST Corporate Broker", withholding=None)
    assert broker["withholding"] is None
    base = {"accountId": account(client, ana, "6500"), "amountCentavos": 1_120_000,
            "vat": "vat", "purchaseType": "services"}
    chosen = bill(client, ana, broker["id"], lines=[base | {"withholding": "WC140"}])
    assert chosen["lines"][0]["withholding"] == "WC140"
    # VAT-exclusive fee is PHP10,000; 15% is PHP1,500, in centavos.
    assert chosen["withheldCentavos"] == 150_000
    unchosen = bill(client, ana, broker["id"], number="TEST-SI-2", lines=[base | {
        "purchaseType": "importation", "withholding": None, "noWithholdingReason": "not_covered"}])
    assert unchosen["withheldCentavos"] == 0
