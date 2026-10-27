"""Purchase classification survives approval and reaches both report formats."""

import runpy
from pathlib import Path

import sqlalchemy as sa

from app import bir_reports as bir
from app.models import Account, JournalEntry, JournalLine
from app.routers.bank import money_accounts
from .test_payables import account, bill, cleared, supplier
from .test_tax_api import ana, app, ben, client  # noqa: F401


def test_mixed_purchase_types_survive_approval_and_reconcile_reports(client, ana, ben):
    s = supplier(client, ben)
    lines = [
        {"accountId": account(client, ben, "6500"), "amountCentavos": 11200 * (i + 1),
         "vat": "vat", "withholding": None, "purchaseType": kind}
        for i, kind in enumerate(bir.payables.PURCHASE_TYPES)
    ]
    # Add a non-VAT service to prove classification doesn't create input VAT.
    lines.append({**lines[0], "amountCentavos": 5000, "vat": "none"})
    b = cleared(client, ana, ben, bill(client, ben, s["id"], lines=lines))
    assert [line["purchaseType"] for line in b["lines"]] == [line["purchaseType"] for line in lines]
    slp = client.get("/finance/bir/lists/slp?year=2026&quarter=4", headers=ana).json()
    r = slp["rows"][0]
    assert r["servicesCentavos"] == 15000 and r["servicesInputTaxCentavos"] == 1200
    assert r["capitalGoodsCentavos"] == 20000 and r["importationInputTaxCentavos"] == 4800
    assert sum(r[f"{bir.camel(k)}Centavos"] for k in bir.payables.PURCHASE_TYPES) == b["netCentavos"]
    assert sum(r[f"{bir.camel(k)}InputTaxCentavos"] for k in bir.payables.PURCHASE_TYPES) == b["vatCentavos"]
    vat = client.get("/finance/bir/returns/vat?year=2026&quarter=4", headers=ana).json()
    values = {line["key"]: line["amountCentavos"] for line in vat["lines"]}
    assert values["services_purchases"] == 15000 and values["importation_input"] == 4800
    assert values["input"] == sum(values[f"{k}_input"] for k in bir.payables.PURCHASE_TYPES)
    csv = client.get("/finance/bir/lists/slp?year=2026&quarter=4&format=csv", headers=ana)
    assert csv.status_code == 200 and "Capital goods: Purchases before VAT" in csv.text
    assert "Services: Input VAT" in csv.text
    bad = client.post("/finance/bills", json={"supplierId": s["id"], "billNumber": "BAD", "billDate": "2026-10-01", "lines": [{**lines[0], "purchaseType": "guess"}]}, headers=ben)
    assert bad.status_code == 422
    assert bill(client, ben, s["id"], number="DEFAULT")["lines"][0]["purchaseType"] == "other_goods"


def test_cash_descendants_including_inactive_accounts_reach_historical_books(app, client, ana):
    from datetime import date

    with app.state.sessions() as db:
        root = Account(code="CASH-T", name=" CASH ", type="asset")
        db.add(root)
        db.flush()
        child = Account(code="CASH-T1", name="Settlement group", type="asset", parent_id=root.id)
        db.add(child)
        db.flush()
        leaf = Account(code="CASH-T2", name="Wallet two", type="asset", parent_id=child.id)
        other = Account(code="OTHER-T", name="Equipment", type="asset")
        db.add_all([leaf, other])
        db.flush()
        entry = JournalEntry(number="TEST-CASH", entry_date=date(2026, 10, 1), memo="Payment", posted_by="Test")
        db.add(entry)
        db.flush()
        db.add_all([JournalLine(entry_id=entry.id, account_id=leaf.id, position=0, credit_centavos=12300),
                    JournalLine(entry_id=entry.id, account_id=other.id, position=1, debit_centavos=12300)])
        db.commit()
        assert leaf.id in {a.id for a in money_accounts(db)}
        assert other.id not in bir.money_accounts(db)
        assert bir.cash_disbursements(db, date(2026, 10, 1), date(2026, 10, 31))["totals"]["amountCentavos"] == 12300
        leaf.is_active = False
        db.commit()
        assert leaf.id not in {a.id for a in money_accounts(db)}
        assert leaf.id in bir.money_accounts(db)
        assert bir.cash_disbursements(db, date(2026, 10, 1), date(2026, 10, 31))["totals"]["amountCentavos"] == 12300


def test_migration_defaults_old_json_lines_without_overwriting_explicit_types(monkeypatch):
    from alembic import op

    engine = sa.create_engine("sqlite://")
    meta = sa.MetaData()
    bills = sa.Table("nbfi_bills", meta, sa.Column("id", sa.String, primary_key=True), sa.Column("lines", sa.JSON))
    meta.create_all(engine)
    original = [{"amountCentavos": 11200}, {"amountCentavos": 22400, "purchaseType": "services"}]
    with engine.begin() as db:
        db.execute(bills.insert().values(id="one", lines=original))
        monkeypatch.setattr(op, "get_bind", lambda: db)
        migration = runpy.run_path(str(Path(__file__).parents[1] / "migrations/versions/0023_bill_purchase_types.py"))
        migration["upgrade"]()
        migration["upgrade"]()
        result = db.scalar(sa.select(bills.c.lines))
        assert result == [{**original[0], "purchaseType": "other_goods"}, original[1]]
