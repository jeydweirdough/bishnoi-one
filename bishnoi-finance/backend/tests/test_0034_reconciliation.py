"""The two distinct 0033 schemas converge, preserving data and rejecting partial schemas."""
from pathlib import Path
import hashlib
import json
import os
import runpy
import shutil
from uuid import uuid4

from alembic import command
from alembic.script import ScriptDirectory
import pytest
import sqlalchemy as sa
from sqlalchemy import text
from app.config import API_DIR
from app.db import make_engine
from app.migrate import _config, upgrade

FEATURE = {'nbfi_petty_cash_vouchers','nbfi_petty_cash_lines','nbfi_petty_cash_events'}
ALL = FEATURE | {'nbfi_recycle_bin'}


@pytest.fixture(params=['sqlite', 'postgresql'])
def engine(request, tmp_path):
    if request.param == 'sqlite':
        e=make_engine('sqlite:///'+(tmp_path/'reconcile.db').as_posix())
        yield e
        e.dispose()
        return
    url=os.environ.get('FINANCE_TEST_POSTGRES_ADMIN_URL')
    if not url: pytest.skip('local PostgreSQL rehearsal not configured')
    admin=make_engine(url, 'pg8000')
    name='finance_0034_'+uuid4().hex
    with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    parsed=sa.engine.make_url(url).set(database=name)
    e=make_engine(parsed.render_as_string(hide_password=False), 'pg8000')
    try:
        yield e
    finally:
        e.dispose()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def source(tmp_path, petty=False):
    location=tmp_path/('feature' if petty else 'main')
    shutil.copytree(API_DIR/'migrations',location)
    (location/'versions/0034_reconcile_petty_cash_and_recycle_bin.py').unlink()
    if petty:
        (location/'versions/0033_recycle_bin.py').unlink()
        shutil.copy2(location/'compat/feature_0033_petty_cash.py',location/'versions/0033_petty_cash.py')
    return location


def start(engine,tmp_path,line):
    old=_config(engine)
    if line!='fresh':
        old.set_main_option('script_location',str(source(tmp_path,line=='feature')))
        command.upgrade(old,'0032' if line=='0032' else '0033')


def snapshot(engine):
    with engine.connect() as c:
        return {t:sorted(repr(tuple(r)) for r in c.execute(text(f'SELECT * FROM "{t}"')))
                for t in sa.inspect(c).get_table_names() if t!='nbfi_alembic_version'}


def seed(engine,line):
    if line=='main':
        with engine.begin() as c:
            c.execute(text("INSERT INTO nbfi_recycle_bin (id,kind,record_id,label,rows,unlinked,deleted_by,deleted_at,expires_at) VALUES ('bin1','synthetic','kept','Synthetic snapshot',:rows,:unlinked,'Synthetic','2026-01-01','2026-02-01')"),{'rows':json.dumps([{'value':'kept'}]),'unlinked':'[]'})
    if line=='feature':
        with engine.begin() as c:
            account=c.execute(text("SELECT id FROM nbfi_accounts WHERE code='1000'")).scalar_one()
            c.execute(text("INSERT INTO nbfi_petty_cash_vouchers (id,number,number_key,status,fund_account_id,voucher_date,amounts_include_vat,net_centavos,vat_centavos,withheld_centavos,total_centavos,paid_out_centavos,created_by,created_at) VALUES ('v1','SYN-1','syn-1','draft',:account,'2026-01-01',true,100,0,0,100,100,'Synthetic','2026-01-01')"),{'account':account})
            c.execute(text("INSERT INTO nbfi_petty_cash_lines (id,voucher_id,position,spent_on,store,receipt_number,account_id,purchase_type,vat,amount_centavos,net_centavos,vat_centavos,withheld_centavos) VALUES ('l1','v1',0,'2026-01-01','Synthetic store','SYN-R1',:account,'services','none',100,100,0,0)"),{'account':account})
            c.execute(text("INSERT INTO nbfi_petty_cash_events (voucher_id,at,kind,who,text) VALUES ('v1','2026-01-01','created','Synthetic','Kept')"))


@pytest.mark.parametrize('line',['fresh','0032','main','feature'])
def test_both_0033_histories_keep_every_row(engine,tmp_path,line):
    start(engine,tmp_path,line)
    seed(engine,line)
    before=snapshot(engine)
    upgrade(engine)
    upgrade(engine)
    after=snapshot(engine)
    assert all(after[t]==rows for t,rows in before.items())
    assert ALL<=after.keys()
    with engine.connect() as c:
        assert c.execute(text('SELECT version_num FROM nbfi_alembic_version')).scalar_one()=='0034'
        if engine.dialect.name=='sqlite':
            assert c.execute(text('PRAGMA integrity_check')).scalar_one()=='ok'
            assert not c.execute(text('PRAGMA foreign_key_check')).all()
    # A second direct 0034 call validates the state where both sets already exist.
    from alembic.operations import Operations
    from alembic.migration import MigrationContext
    with engine.begin() as c:
        step=runpy.run_path(str(API_DIR/'migrations/versions/0034_reconcile_petty_cash_and_recycle_bin.py'))['upgrade']
        step.__globals__['op']=Operations(MigrationContext.configure(c))
        step()
    assert snapshot(engine)==after


@pytest.mark.parametrize('damage', ['partial','column','index','recycle-column','check','fk'])
def test_malformed_schema_stops_before_any_new_table(engine,tmp_path,damage):
    line='main' if damage=='recycle-column' else 'feature'
    start(engine,tmp_path,line)
    with engine.begin() as c:
        if damage=='partial': c.execute(text('DROP TABLE nbfi_petty_cash_events'))
        if damage=='column': c.execute(text('ALTER TABLE nbfi_petty_cash_vouchers RENAME COLUMN notes TO damaged_notes'))
        if damage=='index': c.execute(text('DROP INDEX petty_cash_number_once'))
        if damage=='recycle-column': c.execute(text('ALTER TABLE nbfi_recycle_bin RENAME COLUMN label TO damaged_label'))
        if damage in ('check','fk'):
            # Damage only the constraint being tested in an empty synthetic table.
            meta=sa.MetaData()
            table=sa.Table('nbfi_petty_cash_lines' if damage=='check' else 'nbfi_petty_cash_events',meta,autoload_with=c)
            kind=sa.CheckConstraint if damage=='check' else sa.ForeignKeyConstraint
            constraint=next(x for x in table.constraints if isinstance(x,kind))
            table.constraints.remove(constraint)
            table.drop(c)
            table.create(c)
    before=snapshot(engine)
    with pytest.raises(RuntimeError,match='Incomplete|incompatible'):
        upgrade(engine)
    assert snapshot(engine)==before
    assert ('nbfi_recycle_bin' in snapshot(engine))==(line=='main')
    with engine.connect() as c:
        assert c.execute(text('SELECT version_num FROM nbfi_alembic_version')).scalar_one()=='0033'


def test_original_files_preserved_and_single_head():
    # Allow Git's checkout line endings, but no changes to original content.
    assert hashlib.sha256((API_DIR/'migrations/compat/feature_0033_petty_cash.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()=='5ba7c16cb02f105413309182009fd084e6e1e104796e8d745c1e55bc1161b6b2'
    assert hashlib.sha256((API_DIR/'migrations/versions/0033_recycle_bin.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()=='77b712e4a7ecb73301a2a679d80fa8901403dbaf78a85129a84ae7c2ef892787'
    config=_config(sa.create_engine('sqlite://'))
    script=ScriptDirectory.from_config(config)
    assert script.get_heads()==['0034']
    revisions=list(script.walk_revisions())
    assert len({r.revision for r in revisions})==len(revisions)


def test_plain_combination_reproduces_duplicate_0033(tmp_path):
    location=source(tmp_path)
    shutil.copy2(location/'compat/feature_0033_petty_cash.py',location/'versions/0033_petty_cash.py')
    config=_config(sa.create_engine('sqlite://'))
    config.set_main_option('script_location',str(location))
    with pytest.warns(UserWarning,match='0033 is present more than once'):
        script=ScriptDirectory.from_config(config)
        assert script.get_heads()==['0033','0033']
