from concurrent.futures import ThreadPoolExecutor
import json
import time
from urllib.parse import parse_qs, urlsplit
import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select, func
from app import zoho_connection as zoho
from app.models import Invoice, SalesOrder, JournalEntry
from app.config import Settings
from .test_tax_api import app, client, ana, ben  # noqa: F401


@pytest.fixture
def configured(app, monkeypatch):
    s = app.state.settings
    s.zoho_client_id = SecretStr('fictional-client')
    s.zoho_client_secret = SecretStr('fictional-secret')
    s.zoho_encryption_key = SecretStr(Fernet.generate_key().decode())
    calls = []
    def respond(request):
        calls.append(request)
        if request.url.path == '/oauth/v2/token':
            return httpx.Response(200, json={'access_token': 'fictional-access', 'refresh_token': 'fictional-refresh',
                                            'expires_in': 3600, 'api_domain': 'https://www.zohoapis.com'})
        assert request.method == 'GET' and request.url.path == '/books/v3/organizations'
        return httpx.Response(200, json={'code': 0, 'organizations': [
            {'organization_id': 'fictional-org', 'name': 'Example company', 'currency_code': 'PHP', 'unneeded': 'discard'}]})
    original = httpx.Client
    monkeypatch.setattr(zoho.httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    return s, calls


def start(client, ana):
    r = client.post('/finance/integrations/zoho/start', headers=ana)
    assert r.status_code == 200, r.text
    return parse_qs(urlsplit(r.json()['url']).query)


def connect(client, ana):
    q = start(client, ana)
    body = {'state': q['state'][0], 'code': 'fictional-code'}
    r = client.post('/finance/integrations/zoho/callback', headers=ana, json=body)
    assert r.status_code == 200, r.text
    return body


def test_unconfigured_and_permissions(client, ana, ben):
    r = client.get('/finance/integrations/zoho', headers=ana)
    assert r.status_code == 200 and not r.json()['configured']
    for path in ('', '/start', '/check', '/organization', '/disconnect', '/callback'):
        r = client.get('/finance/integrations/zoho', headers=ben) if path == '' else client.post('/finance/integrations/zoho'+path, headers=ben, json={})
        assert r.status_code == 403
    assert client.post('/finance/integrations/zoho/start', headers=ana).status_code == 503


def test_authorization_encrypted_storage_org_selection_no_transactions(client, ana, app, configured):
    s, calls = configured
    q = start(client, ana)
    assert set(q['scope'][0].split(',')) == set(zoho.SCOPES)
    assert q['access_type'] == ['offline'] and q['redirect_uri'] == [s.zoho_redirect_uri]
    body = {'state': q['state'][0], 'code': 'fictional-code'}
    assert client.post('/finance/integrations/zoho/callback', headers=ana, json=body).status_code == 200
    assert client.post('/finance/integrations/zoho/callback', headers=ana, json=body).status_code == 400
    assert client.post('/finance/integrations/zoho/check', headers=ana).json()['organizations'] == [
        {'id': 'fictional-org', 'name': 'Example company', 'currency': 'PHP'}]
    endpoint = '/finance/integrations/zoho/organization'
    assert client.post(endpoint, headers=ana, json={'organizationId': 'unknown'}).status_code == 422
    assert client.post(endpoint, headers=ana, json={'organizationId': 'fictional-org'}).status_code == 200
    status = client.get('/finance/integrations/zoho', headers=ana)
    assert status.json()['organization']['id'] == 'fictional-org'
    assert 'fictional-access' not in status.text and 'fictional-refresh' not in status.text
    _, _, path = zoho.configuration(s)
    encrypted = path.read_bytes()
    assert b'fictional-access' not in encrypted and b'fictional-refresh' not in encrypted
    assert b'fictional-code' not in encrypted
    record = json.loads(Fernet(s.zoho_encryption_key.get_secret_value()).decrypt(encrypted))
    assert record['connection']['refresh'] == 'fictional-refresh'
    assert all(r.method == 'GET' or r.url.path == '/oauth/v2/token' for r in calls)
    with app.state.sessions() as db:
        for model in (Invoice, SalesOrder, JournalEntry):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    assert client.post('/finance/integrations/zoho/disconnect', headers=ana).status_code == 200
    assert not client.get('/finance/integrations/zoho', headers=ana).json()['authorized']


def test_state_bound_expiring_and_denial_consumed(configured):
    s, calls = configured
    result = zoho.start(s, 'actor', 'session')
    state = parse_qs(urlsplit(result['url']).query)['state'][0]
    with pytest.raises(Exception) as failure:
        zoho.complete(s, 'actor', 'other-session', state, 'code', None)
    assert failure.value.status_code == 400 and calls == []
    with pytest.raises(Exception):
        zoho.complete(s, 'actor', 'session', state, None, 'access_denied')
    with pytest.raises(Exception):
        zoho.complete(s, 'actor', 'session', state, 'code', None)
    assert calls == []
    state = parse_qs(urlsplit(zoho.start(s, 'actor', 'session')['url']).query)['state'][0]
    with zoho.locked(s) as record:
        for pending in record['pending'].values():
            pending['until'] = time.time() - 1
    with pytest.raises(Exception):
        zoho.complete(s, 'actor', 'session', state, 'code', None)
    assert calls == []


def test_failed_exchange_consumes_state_preserves_previous_connection(client, ana, configured, monkeypatch):
    s, calls = configured
    connect(client, ana)
    state = start(client, ana)['state'][0]
    monkeypatch.setattr(zoho, 'token_request', lambda *args: (_ for _ in ()).throw(zoho.HTTPException(502, 'Temporary failure')))
    body = {'state': state, 'code': 'new-code'}
    assert client.post('/finance/integrations/zoho/callback', headers=ana, json=body).status_code == 502
    assert client.post('/finance/integrations/zoho/callback', headers=ana, json=body).status_code == 400
    assert client.get('/finance/integrations/zoho', headers=ana).json()['authorized']


def test_refresh_singleflight_and_persisted_across_checks(client, ana, configured):
    s, calls = configured
    connect(client, ana)
    with zoho.locked(s) as record:
        record['connection']['expires'] = 0
    def check():
        with zoho.locked(s) as record:
            return zoho.organizations(s, record)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(list(pool.map(lambda _: check(), range(2))))
    assert len([r for r in calls if r.url.path == '/oauth/v2/token']) == 2  # initial grant + one refresh


def test_binding_tamper_and_production_fail_closed(client, ana, configured):
    s, _ = configured
    connect(client, ana)
    original = s.zoho_client_id
    s.zoho_client_id = SecretStr('another-client')
    with pytest.raises(zoho.HTTPException) as failure:
        zoho.status(s)
    assert failure.value.status_code == 409
    s.zoho_client_id = original
    _, _, path = zoho.configuration(s)
    path.write_bytes(b'tampered')
    with pytest.raises(zoho.HTTPException) as failure:
        zoho.status(s)
    assert failure.value.status_code == 503
    production = Settings(_env_file=None, environment='production')
    assert not zoho.status(production)['configured']
    assert 'local-only' in zoho.status(production)['message']


def test_domains_and_redirects_are_not_provider_controlled(configured, monkeypatch):
    s, _ = configured
    for uri in ('http://evil.example/callback', s.zoho_redirect_uri+'?code=secret', 'https://user:pass@example.com'+zoho.CALLBACK_PATH):
        s.zoho_redirect_uri = uri
        with pytest.raises(zoho.HTTPException):
            zoho.configuration(s)
    s.zoho_redirect_uri = 'http://localhost:4301'+zoho.CALLBACK_PATH
    original = httpx.Client
    # This test runs after configured has wrapped the class; replace with a minimal client.
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            return httpx.Response(200, json={'access_token': 'fake', 'api_domain': 'https://evil.example'})
    monkeypatch.setattr(zoho.httpx, 'Client', Client)
    with pytest.raises(zoho.HTTPException) as failure:
        zoho.token_request(s, {})
    assert failure.value.status_code == 409

def test_errors_preserve_tokens_and_retry_only_one_401(client, ana, configured, monkeypatch):
    s, _ = configured
    connect(client, ana)
    class Client:
        status = 429
        reads = 0
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, *args, **kwargs):
            Client.reads += 1
            if Client.status == 401 and Client.reads == 2:
                return httpx.Response(200, json={'code': 0, 'organizations': []})
            return httpx.Response(Client.status, json={'code': 99})
        def post(self, url, data):
            assert url.endswith('/oauth/v2/token') and data['grant_type'] == 'refresh_token'
            return httpx.Response(200, json={'access_token': 'renewed-access', 'expires_in': 3600})
    monkeypatch.setattr(zoho.httpx, 'Client', Client)
    for code in (429, 403):
        Client.status, Client.reads = code, 0
        with zoho.locked(s) as record:
            with pytest.raises(zoho.HTTPException) as failure:
                zoho.organizations(s, record)
            assert failure.value.status_code == (429 if code == 429 else 409)
            assert record['connection']['refresh'] == 'fictional-refresh'
        assert Client.reads == 1
    Client.status, Client.reads = 401, 0
    with zoho.locked(s) as record:
        assert zoho.organizations(s, record) == []
        assert record['connection']['access'] == 'renewed-access'
    assert Client.reads == 2
