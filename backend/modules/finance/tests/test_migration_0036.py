"""0036 drops foreign-currency bills (owner's decision, 2026-11-17), but never silently: while a bill or voucher
still holds a foreign currency, a rate or an exchange difference, it refuses and changes nothing."""
import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from modules.finance.migrate import _config

SUPPLIER = "INSERT INTO nbfi_suppliers(id,name,vat_registered,terms_days,is_active,created_at,created_by) VALUES ('s1','Synthetic supplier',1,30,1,'2026-01-01','Synthetic')"
BILL = ("INSERT INTO nbfi_bills(id,status,supplier_id,bill_number,bill_date,due_date,checked_po,checked_dr,amounts_include_vat,lines,net_centavos,"
        "vat_centavos,withheld_centavos,total_centavos,payable_centavos,paid_centavos,created_at,created_by,currency,rate_e4) VALUES "
        "('b1','draft','s1','SYN-1','2026-01-01','2026-02-01',0,0,1,'[]',100,0,0,100,100,0,'2026-01-01','Synthetic',:currency,:rate)")


def at_0035(tmp_path, currency, rate):
    engine = create_engine("sqlite:///" + (tmp_path / "f.db").as_posix())
    command.upgrade(_config(engine), "0035")
    with engine.begin() as c:
        c.execute(text(SUPPLIER))
        c.execute(text(BILL), {"currency": currency, "rate": rate})
    return engine


@pytest.mark.parametrize("currency,rate", [("USD", 560000), ("PHP", 560000)])
def test_a_foreign_bill_stops_the_upgrade_and_nothing_changes(tmp_path, currency, rate):
    engine = at_0035(tmp_path, currency, rate)
    with pytest.raises(RuntimeError, match="bill"):
        command.upgrade(_config(engine), "head")
    with engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM nbfi_alembic_version")).scalar() == "0035"
        assert {"currency", "rate_e4"} <= {x["name"] for x in inspect(c).get_columns("nbfi_bills")}
        assert c.execute(text("SELECT currency, rate_e4 FROM nbfi_bills")).one() == (currency, rate)
    engine.dispose()


def test_peso_bills_upgrade_and_keep_their_money(tmp_path):
    engine = at_0035(tmp_path, "PHP", None)
    command.upgrade(_config(engine), "head")
    with engine.connect() as c:
        assert not {"currency", "rate_e4", "foreign_total", "foreign_payable"} & {x["name"] for x in inspect(c).get_columns("nbfi_bills")}
        assert "nbfi_exchange_rates" not in inspect(c).get_table_names()
        assert c.execute(text("SELECT id, payable_centavos FROM nbfi_bills")).one() == ("b1", 100)
    engine.dispose()
