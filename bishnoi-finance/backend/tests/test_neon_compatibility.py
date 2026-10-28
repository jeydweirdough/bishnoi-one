"""Temporary synthetic databases only. Never uses the staged official Neon URL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, datetime, timezone
import json
import struct
from types import SimpleNamespace
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from fastapi import HTTPException
from sqlalchemy import select, func
from app import zoho_connection as oauth, zoho_storage as storage, zoho_runtime as runtime
from app.models import ZohoConnection, ZohoRuntime, Invoice, Bill, JournalEntry
from app.postgres_driver import connection_options, channel_bound_connection
from .test_tax_api import app, client, ana, ben  # noqa: F401


@pytest.fixture
def persistent(app, monkeypatch):
    settings=app.state.settings
    settings.database_url='postgresql://synthetic:secret@db.invalid/finance?sslmode=require'
    settings.zoho_database_enabled=True
    settings.zoho_connection_id='synthetic-finance'
    settings.zoho_environment='isolated-test'
    settings.zoho_worker_enabled=True
    settings.zoho_client_id=SecretStr('synthetic-client')
    settings.zoho_client_secret=SecretStr('synthetic-secret')
    settings.zoho_encryption_key=SecretStr(Fernet.generate_key().decode())
    monkeypatch.setattr(storage,'factory',lambda s:app.state.sessions)
    monkeypatch.setattr(runtime,'factory',lambda s:app.state.sessions)
    return settings


def authorised(settings):
    with oauth.locked(settings) as record:
        record['connection']={'access':'synthetic-access-token','refresh':'synthetic-refresh-token',
            'expires':9999999999,'connectedAt':1,'organization':{'id':'org','name':'Synthetic company','currency':'PHP'}}


def test_tls_and_url_options_fail_closed_without_echoing_secrets():
    url,binding,options=connection_options('postgresql://test:p%40ss@localhost/test?sslmode=require&channel_binding=require')
    assert options['password']=='p@ss' and binding=='require'
    assert options['ssl_context'].check_hostname and options['ssl_context'].verify_mode==2
    for query in ('sslmode=disable','channel_binding=disable','connect_timeout=0','connect_timeout=100','options=private-token','sslmode=require&sslmode=disable'):
        with pytest.raises(ValueError) as failure:connection_options('postgresql://test:secret@localhost/test?'+query)
        assert 'private-token' not in str(failure.value) and 'postgresql://' not in str(failure.value)


def test_required_channel_binding_rejects_plain_authentication(monkeypatch):
    from pg8000.dbapi import InterfaceError,Connection
    secured=channel_bound_connection(True)
    instance=secured.__new__(secured);instance._finance_scram_plus=False
    for data in (struct.pack('!i',0),struct.pack('!i',3),struct.pack('!i',10)+b'SCRAM-SHA-256\0\0'):
        with pytest.raises(InterfaceError):instance.handle_AUTHENTICATION_REQUEST(data,{})
    def pretend_plain(self,data,context):self.auth=SimpleNamespace(mechanism_name='SCRAM-SHA-256')
    monkeypatch.setattr(Connection,'handle_AUTHENTICATION_REQUEST',pretend_plain)
    with pytest.raises(InterfaceError):instance.handle_AUTHENTICATION_REQUEST(struct.pack('!i',10)+b'SCRAM-SHA-256-PLUS\0\0',{})


def test_database_storage_needs_explicit_environment_enable(app):
    s=app.state.settings;s.database_url='postgresql://test:secret@db.invalid/finance'
    result=oauth.status(s)
    assert not result['configured'] and 'not enabled' in result['message']


def test_encrypted_snapshot_read_is_non_mutating_and_password_rotation_safe(app,persistent):
    s=persistent
    assert not oauth.status(s)['authorized']
    with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(ZohoConnection))==0
    authorised(s)
    with app.state.sessions() as db:
        row=db.get(ZohoConnection,s.zoho_connection_id);encrypted,revision=row.encrypted,row.revision
    assert 'synthetic-refresh-token' not in encrypted and 'synthetic-access-token' not in encrypted
    s.database_url=s.database_url.replace(':secret@',':rotated@')
    assert oauth.status(s)['authorized']
    with app.state.sessions() as db:
        row=db.get(ZohoConnection,s.zoho_connection_id)
        assert row.revision==revision and row.encrypted==encrypted
        for model in (Invoice,Bill,JournalEntry):assert db.scalar(select(func.count()).select_from(model))==0
    s.database_url=s.database_url.replace('db.invalid','another.invalid')
    with pytest.raises(HTTPException) as failure:oauth.saved_record(s)
    assert failure.value.status_code==409


def test_wrong_key_does_not_overwrite_saved_ciphertext(app,persistent):
    authorised(persistent)
    with app.state.sessions() as db:before=db.get(ZohoConnection,persistent.zoho_connection_id).encrypted
    persistent.zoho_encryption_key=SecretStr(Fernet.generate_key().decode())
    with pytest.raises(HTTPException):
        with oauth.locked(persistent):pass
    with app.state.sessions() as db:assert db.get(ZohoConnection,persistent.zoho_connection_id).encrypted==before


def test_database_state_single_use_and_bound_to_actor(persistent,monkeypatch):
    from urllib.parse import urlsplit,parse_qs
    state=parse_qs(urlsplit(oauth.start(persistent,'person','session')['url']).query)['state'][0]
    with pytest.raises(HTTPException):oauth.complete(persistent,'other','session',state,None,'denied')
    monkeypatch.setattr(oauth,'token_request',lambda *a: (_ for _ in ()).throw(HTTPException(502,'Synthetic exchange failure')))
    with pytest.raises(HTTPException) as first:oauth.complete(persistent,'person','session',state,'code',None)
    assert first.value.status_code==502
    with pytest.raises(HTTPException) as second:oauth.complete(persistent,'person','session',state,'code',None)
    assert second.value.status_code==400


def test_database_lock_serialises_refresh_state(persistent):
    authorised(persistent)
    def change():
        with oauth.locked(persistent) as r:r['counter']=r.get('counter',0)+1
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda _:change(),range(6)))
    assert oauth.saved_record(persistent)['counter']==6


def test_status_explains_database_storage_without_provider_calls(client,ana,ben,persistent):
    authorised(persistent)
    response=client.get('/finance/integrations/zoho',headers=ana)
    assert response.status_code==200
    data=response.json()
    assert not data['localOnly'] and data['storage']=='Encrypted database storage'
    assert data['sourceSync']['state']=='not-started' and data['worker']['state']=='not-started'
    assert 'synthetic-access-token' not in response.text and 'synthetic-refresh-token' not in response.text
    assert client.get('/finance/integrations/zoho',headers=ben).status_code==403


def test_request_reservations_persist_and_pause_fences_old_owner(persistent):
    s=persistent
    assert runtime.status(s,'org')['state']=='not-started'
    with runtime.worker(s,'org'):
        runtime.reserve(s,'org',2);runtime.reserve(s,'org',2)
        with pytest.raises(HTTPException) as failure:runtime.reserve(s,'org',2)
        assert failure.value.status_code==429
        assert runtime.status(s,'org')['requestsToday']==2
        runtime.pause(s,'org',True)
        with pytest.raises(HTTPException):
            with runtime.fence(s,'org'):pytest.fail('Stale worker must not publish')
    assert runtime.status(s,'org')['state']=='paused'
    runtime.pause(s,'org',False)
    with runtime.worker(s,'org'):
        with pytest.raises(HTTPException):runtime.reserve(s,'org',2)


def test_worker_exclusion_expiry_and_old_owner_release(app,persistent):
    s=persistent
    with runtime.worker(s,'org'):
        with pytest.raises(HTTPException):
            with runtime.worker(s,'org'):pytest.fail('Second active worker')
        with runtime.row(s,'org') as (row,now):row.lease_until=now-timedelta(seconds=1)
        with pytest.raises(HTTPException):runtime.reserve(s,'org',10)
        with runtime.worker(s,'org'):runtime.reserve(s,'org',10)
    assert runtime.status(s,'org')['state']=='idle'


def test_updater_control_requires_permission_and_local_mode_is_not_modified(client,ana,ben):
    assert client.post('/finance/integrations/zoho/updater',headers=ben,json={'paused':True}).status_code==403
    assert client.post('/finance/integrations/zoho/updater',headers=ana,json={'paused':True}).status_code==409


def test_upgrade_from_0022_preserves_all_existing_columns_and_rows(tmp_path):
    from alembic import command
    from app.db import make_engine
    from app.migrate import _config
    from sqlalchemy import MetaData, Table
    engine=make_engine('sqlite:///'+(tmp_path/'old-finance.db').as_posix())
    command.upgrade(_config(engine),'0022')
    before_meta=MetaData();before_meta.reflect(engine)
    with engine.begin() as db:
        db.execute(before_meta.tables['nbfi_suppliers'].insert().values(id='supplier',name='Synthetic supplier',
            vat_registered=False,terms_days=30,is_active=True,created_by='Synthetic operator',created_at=datetime.now(timezone.utc)))
    def snapshot():
        with engine.connect() as db:
            return {name: sorted([repr(tuple(r)) for r in db.execute(select(*table.c))])
                for name,table in before_meta.tables.items() if name!='nbfi_alembic_version'}
    before=snapshot()
    command.upgrade(_config(engine),'head')
    assert snapshot()==before
    with engine.connect() as db:
        assert db.scalar(select(func.count()).select_from(ZohoConnection))==0
        assert db.scalar(select(func.count()).select_from(ZohoRuntime))==0
        supplier=db.execute(__import__('sqlalchemy').text('SELECT tax_defaults_confirmed,import_details FROM nbfi_suppliers')).one()
        assert supplier[0]==0 and json.loads(supplier[1])=={}
    engine.dispose()
