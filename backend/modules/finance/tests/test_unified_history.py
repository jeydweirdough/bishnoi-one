"""Recognized legacy branch shapes must upgrade, incomplete/mixed ones must stop."""
from pathlib import Path
import runpy
import pytest
from alembic import command
from alembic.operations import Operations
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text, inspect
from modules.finance.config import API_DIR
from modules.finance.migrate import _config, upgrade

def apply_step(connection,name):
    step=runpy.run_path(str(API_DIR/'migrations/versions'/name))['upgrade']
    step.__globals__['op']=Operations(MigrationContext.configure(connection));step()

def old_branch(tmp_path,revision):
    engine=create_engine('sqlite:///'+(tmp_path/'legacy.db').as_posix())
    command.upgrade(_config(engine),'0035')
    with engine.begin() as c:
        apply_step(c,'0038_supplier_review_fields.py')
        if revision in ('0037','0038'):apply_step(c,'0039_company_review.py')
        if revision=='0038':apply_step(c,'0040_purchase_intakes.py')
        c.execute(text('UPDATE nbfi_alembic_version SET version_num=:r'),{'r':revision})
        c.execute(text('CREATE TABLE preservation_probe(value TEXT)'))
        c.execute(text("INSERT INTO preservation_probe VALUES ('fictional saved row')"))
    return engine

@pytest.mark.parametrize('revision',['0036','0037','0038'])
def test_each_recognized_legacy_branch_preserves_rows_and_converges(tmp_path,revision):
    engine=old_branch(tmp_path,revision)
    upgrade(engine);upgrade(engine)
    with engine.connect() as c:
        assert c.execute(text('SELECT value FROM preservation_probe')).scalar_one()=='fictional saved row'
        assert c.execute(text('SELECT version_num FROM nbfi_alembic_version')).scalar_one()=='0040'
        assert c.execute(text('PRAGMA integrity_check')).scalar_one()=='ok'
        assert not c.execute(text('PRAGMA foreign_key_check')).all()
        assert 'origin' in {x['name'] for x in inspect(c).get_columns('nbfi_suppliers')}
        assert 'nbfi_purchase_intakes' in inspect(c).get_table_names()

def test_partial_legacy_history_refuses_and_restores_version(tmp_path):
    engine=old_branch(tmp_path,'0038')
    with engine.begin() as c:c.execute(text('ALTER TABLE nbfi_purchase_intakes RENAME COLUMN digest TO damaged_digest'))
    with pytest.raises(RuntimeError,match='Partial legacy table columns'):upgrade(engine)
    with engine.connect() as c:
        assert c.execute(text('SELECT version_num FROM nbfi_alembic_version')).scalar_one()=='0038'
        assert 'currency' in {x['name'] for x in inspect(c).get_columns('nbfi_bills')}
        assert c.execute(text('SELECT value FROM preservation_probe')).scalar_one()=='fictional saved row'

def test_refused_main_step_restores_legacy_revision(tmp_path):
    engine=old_branch(tmp_path,'0038')
    # The same safety boundary must restore even when a main migration refuses.
    from modules.finance import migrate
    def refuse(config,revision):
        raise RuntimeError('foreign money requires separate review')
    with pytest.MonkeyPatch.context() as m:
        m.setattr(migrate.command,'upgrade',refuse)
        with pytest.raises(RuntimeError,match='foreign money'):upgrade(engine)
    with engine.connect() as c:
        assert c.execute(text('SELECT version_num FROM nbfi_alembic_version')).scalar_one()=='0038'
        assert c.execute(text('SELECT value FROM preservation_probe')).scalar_one()=='fictional saved row'
