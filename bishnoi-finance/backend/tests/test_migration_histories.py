"""Both issued migration histories must reach one schema without losing records."""
from pathlib import Path
import json
import shutil
import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine,inspect,text
from app.config import API_DIR
from app.migrate import _config


@pytest.fixture
def feature_history(tmp_path):
    source=API_DIR/'migrations'
    destination=tmp_path/'legacy_feature_migrations'
    shutil.copytree(source,destination)
    for name in ('0023_account_term.py','0024_cost_of_goods_sold.py','0025_invoice_division.py','0026_business_events.py'):
        (destination/'versions'/name).unlink()
    # The feature history ended at 0028: 0029 (the reconciliation) and everything after it came later.
    for file in (destination/'versions').glob('[0-9][0-9][0-9][0-9]_*.py'):
        if int(file.name[:4])>=29:file.unlink()
    for file in (source/'compat').glob('feature_*.py'):
        shutil.copy2(file,destination/'versions'/file.name.removeprefix('feature_'))
    return destination


@pytest.mark.parametrize('history,revision', [('main',n) for n in range(23,27)]+[('feature',n) for n in range(22,29)])
def test_both_histories_preserve_values_and_relationships(tmp_path,feature_history,history,revision):
    engine=create_engine('sqlite:///'+(tmp_path/'synthetic.db').as_posix())
    old=_config(engine)
    if history=='feature':old.set_main_option('script_location',str(feature_history))
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
        assert {'nbfi_sales_orders','nbfi_zoho_source_documents','nbfi_zoho_source_runs','nbfi_events_in','nbfi_events_out'}<=tables
        for table,names in {'nbfi_accounts':{'term'},'nbfi_invoices':{'cost_centavos','line_costs','division_id','team_id'},'nbfi_suppliers':{'tax_defaults_confirmed','import_details'},'nbfi_bills':{'tax_reviewed'}}.items():
            assert names<={x['name'] for x in inspect(c).get_columns(table)}
        assert not c.execute(text('PRAGMA foreign_key_check')).all()
        assert c.execute(text('select version_num from nbfi_alembic_version')).scalar()==ScriptDirectory.from_config(_config(engine)).get_current_head()
    engine.dispose()
