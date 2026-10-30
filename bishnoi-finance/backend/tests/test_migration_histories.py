"""Every issued Finance migration history must reach one schema without losing records.

Main and the feature branch twice issued the same numbers for different changes (0023-0026 on
2026-10-27; 0027-0029 on 2026-10-29). The chain keeps main's files; the feature's are in
migrations/compat; 0029 (feature) and 0032 supply whichever schema a database lacks. A database
can be at any revision of any of these lines:
- main: main's 0023-0029 (e.g. a database Jade's code upgraded);
- feature-old: the feature's 0023-0028, before the first reconciliation;
- ours: main's 0023-0026, then the feature's 0027-0029, 0030, 0031 (official and the testing site
  on 2026-10-29).
"""
from pathlib import Path
import json
import shutil
import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine,inspect,text
from app.config import API_DIR
from app.migrate import _config

MAIN_0023_0026=('0023_account_term','0024_cost_of_goods_sold','0025_invoice_division','0026_business_events')
MAIN_0027_0029=('0027_invoices_from_deliveries','0028_banks_payments_equity','0029_management_reports')


def history(tmp_path,name,drop,add,last):
    """A copy of the migrations as a past line had them: main's files in `drop` out, the feature's
    compat files numbered in `add` in, nothing after `last`."""
    source=API_DIR/'migrations'
    destination=tmp_path/f'{name}_migrations'
    shutil.copytree(source,destination)
    versions=destination/'versions'
    for step in drop:
        (versions/f'{step}.py').unlink()
    for file in versions.glob('[0-9][0-9][0-9][0-9]_*.py'):
        if int(file.name[:4])>last:file.unlink()
    for number in add:
        [file]=(source/'compat').glob(f'feature_{number:04}_*.py')
        shutil.copy2(file,versions/file.name.removeprefix('feature_'))
    return destination


LINES={
    'main':lambda tmp:None,  # the chain itself, stopped part-way
    'feature-old':lambda tmp:history(tmp,'feature_old',MAIN_0023_0026+MAIN_0027_0029,range(23,29),28),
    'ours':lambda tmp:history(tmp,'ours',MAIN_0027_0029,range(27,30),31),
}
CASES=[('main',n) for n in range(23,30)]+[('feature-old',n) for n in range(22,29)]+[('ours',n) for n in range(27,32)]


@pytest.mark.parametrize('line,revision',CASES)
def test_every_history_reaches_one_schema_and_keeps_records(tmp_path,line,revision):
    engine=create_engine('sqlite:///'+(tmp_path/'synthetic.db').as_posix())
    old=_config(engine)
    location=LINES[line](tmp_path)
    if location:old.set_main_option('script_location',str(location))
    command.upgrade(old,'0022')
    with engine.begin() as c:
        c.execute(text("INSERT INTO nbfi_suppliers(id,name,vat_registered,terms_days,is_active,created_at,created_by) VALUES ('s1','Synthetic supplier',1,30,1,'2026-01-01','Synthetic')"))
        c.execute(text("INSERT INTO nbfi_bills(id,status,supplier_id,bill_number,bill_date,due_date,checked_po,checked_dr,amounts_include_vat,lines,net_centavos,vat_centavos,withheld_centavos,total_centavos,payable_centavos,paid_centavos,created_at,created_by) VALUES ('b1','draft','s1','SYN-1','2026-01-01','2026-02-01',0,0,1,:lines,100,0,0,100,100,0,'2026-01-01','Synthetic')"),{'lines':json.dumps([{'description':'Kept','purchaseType':'services'}])})
    command.upgrade(old,f'{revision:04}')
    with engine.connect() as c:
        before={table:[dict(row._mapping) for row in c.execute(text(f'SELECT * FROM "{table}"'))] for table in inspect(c).get_table_names() if table!='nbfi_alembic_version'}
    command.upgrade(_config(engine),'head')
    command.upgrade(_config(engine),'head')
    with engine.connect() as c:
        for table,rows in before.items():
            after=[dict(row._mapping) for row in c.execute(text(f'SELECT * FROM "{table}"'))]
            assert len(after)==len(rows),table
            assert [{k:r[k] for k in rows[0]} for r in after]==rows if rows else not after
        tables=set(inspect(c).get_table_names())
        # Both lines' tables: the feature's (sales orders, Zoho cache, connection, delivery queue, imports)
        # and main's (business events, bank accounts, exchange rates, year closings, fixed assets, budgets).
        assert {'nbfi_sales_orders','nbfi_zoho_source_documents','nbfi_zoho_source_runs','nbfi_zoho_connections','nbfi_zoho_runtime',
                'nbfi_zoho_deliveries','nbfi_zoho_links','nbfi_zoho_delivery_events','nbfi_import_matches','nbfi_import_runs',
                'nbfi_import_records','nbfi_import_rules','nbfi_events_in','nbfi_events_out','nbfi_bank_accounts',
                'nbfi_exchange_rates','nbfi_year_closings','nbfi_fixed_assets','nbfi_budgets'}<=tables
        for table,names in {'nbfi_accounts':{'term','cost_behaviour','report_tag'},
                            'nbfi_invoices':{'cost_centavos','line_costs','division_id','team_id','delivery_id','sales_order_id','attention'},
                            'nbfi_suppliers':{'tax_defaults_confirmed','import_details'},'nbfi_bills':{'tax_reviewed','currency','rate_e4'},
                            'nbfi_payment_vouchers':{'rate_e4','exchange_centavos','bank_account_id'},
                            'nbfi_ledger_settings':{'auto_invoice','locked_until','fx_gain_account_id'},
                            'nbfi_import_matches':{'per_record'}}.items():
            assert names<={x['name'] for x in inspect(c).get_columns(table)},table
        assert not c.execute(text('PRAGMA foreign_key_check')).all()
        assert c.execute(text('select version_num from nbfi_alembic_version')).scalar()==ScriptDirectory.from_config(_config(engine)).get_current_head()=='0033'
    engine.dispose()
