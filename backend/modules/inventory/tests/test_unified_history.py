"""Legacy receipt0024 and fresh SQLite backup/rollback retain every saved probe row."""
import sqlite3
import runpy
import pytest
from alembic import command
from alembic.operations import Operations
from alembic.migration import MigrationContext
from sqlalchemy import create_engine,text
from modules.inventory import migrate
from modules.inventory.config import API_DIR

def old_branch(tmp_path):
    file=tmp_path/'inventory.db';engine=create_engine('sqlite:///'+file.as_posix())
    command.upgrade(migrate._config(engine),'0023')
    with engine.begin() as c:
        step=runpy.run_path(str(API_DIR/'migrations/versions/0032_receipt_finance.py'))['upgrade']
        step.__globals__['op']=Operations(MigrationContext.configure(c));step()
        c.execute(text("UPDATE nbin_alembic_version SET version_num='0024'"))
        c.execute(text('CREATE TABLE preservation_probe(value TEXT)'))
        c.execute(text("INSERT INTO preservation_probe VALUES ('fictional saved row')"))
    return file,engine

def test_old_receipt_history_converges_without_losing_rows(tmp_path):
    _,engine=old_branch(tmp_path)
    migrate.upgrade(engine);migrate.upgrade(engine)
    with engine.connect() as c:
        assert c.execute(text('SELECT value FROM preservation_probe')).scalar_one()=='fictional saved row'
        assert c.execute(text('SELECT version_num FROM nbin_alembic_version')).scalar_one()=='0033'
        assert c.execute(text('PRAGMA integrity_check')).scalar_one()=='ok'
        assert not c.execute(text('PRAGMA foreign_key_check')).all()

def test_failed_upgrade_restores_wal_rows_and_legacy_revision(tmp_path,monkeypatch):
    file,engine=old_branch(tmp_path);engine.dispose()
    writer=sqlite3.connect(file)
    writer.execute('PRAGMA journal_mode=WAL');writer.execute('PRAGMA wal_autocheckpoint=0')
    writer.execute("INSERT INTO preservation_probe VALUES ('fictional WAL row')");writer.commit()
    def half_done(config,revision):
        with engine.begin() as c:c.execute(text('CREATE TABLE half_done(value TEXT)'))
        raise RuntimeError('fictional upgrade refused')
    monkeypatch.setattr(migrate.command,'upgrade',half_done)
    try:
        with pytest.raises(RuntimeError,match='fictional upgrade refused'):migrate.upgrade(engine)
    finally:writer.close()
    with sqlite3.connect(file) as db:
        assert db.execute('SELECT count(*) FROM preservation_probe').fetchone()[0]==2
        assert db.execute('SELECT version_num FROM nbin_alembic_version').fetchone()[0]=='0024'
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='half_done'").fetchall()
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
