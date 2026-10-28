"""Dedicated, read-only Zoho OAuth. Local encrypted storage until shared hosting is agreed.

One Finance database represents one company. Never expose tokens or accept arbitrary URLs.
No transaction ingestion or business-write HTTP methods exist in this module.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
from urllib.parse import urlencode, urlsplit
from app import zoho_storage

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
import httpx

SCOPES = tuple('ZohoBooks.' + area + '.READ' for area in
               ('salesorders', 'invoices', 'contacts', 'customerpayments', 'settings'))
OUTBOUND_SCOPES = SCOPES + ('ZohoBooks.bills.READ','ZohoBooks.bills.CREATE',
                            'ZohoBooks.vendorpayments.READ','ZohoBooks.vendorpayments.CREATE')
REGIONS = {suffix: (f'https://accounts.zoho.{suffix}', f'https://www.zohoapis.{suffix}')
           for suffix in ('com', 'eu', 'in', 'com.au', 'jp', 'ca', 'com.cn')}
CALLBACK_PATH = '/finance/integrations/zoho/callback'


def configuration(settings):
    database = zoho_storage.database_mode(settings)
    if settings.is_production and not database:
        raise HTTPException(503, 'Zoho connection is local-only until persistent shared secret storage is configured.')
    if database and (not settings.zoho_database_enabled or not settings.zoho_connection_id or not settings.zoho_environment):
        raise HTTPException(503, 'PostgreSQL Zoho storage is not enabled for this environment. IT must complete the reviewed setup first.')
    if database and (len(settings.zoho_connection_id) > 80 or len(settings.zoho_environment) > 80):
        raise HTTPException(503, 'Choose a short, stable Zoho connection and environment name.')
    if not all((settings.zoho_client_id, settings.zoho_client_secret, settings.zoho_encryption_key)):
        raise HTTPException(503, 'Run the local Zoho setup helper first, then restart the Finance API.')
    if settings.zoho_region not in REGIONS:
        raise HTTPException(503, 'Choose a supported Zoho data centre in the backend settings.')
    uri = urlsplit(settings.zoho_redirect_uri)
    if (uri.path != CALLBACK_PATH or uri.query or uri.fragment or uri.username or uri.password
            or not (uri.scheme == 'https' or (uri.scheme == 'http' and uri.hostname in ('localhost', '127.0.0.1')))):
        raise HTTPException(503, 'The configured Zoho callback address is invalid.')
    try:
        cipher = Fernet(settings.zoho_encryption_key.get_secret_value().encode())
    except (ValueError, TypeError):
        raise HTTPException(503, 'The local Zoho encryption key is invalid.') from None
    address = settings.database_url
    if database:
        from sqlalchemy.engine import make_url
        url = make_url(address)
        # Bind to the endpoint/environment, never the password (which may rotate).
        address = '|'.join([url.host or '', str(url.port or 5432), url.database or '',
                            settings.zoho_environment, settings.zoho_connection_id])
    fingerprint = hashlib.sha256((address + '|' + settings.zoho_client_id.get_secret_value()
                                  + '|' + settings.zoho_region + '|' + settings.zoho_redirect_uri).encode()).hexdigest()
    path = None if database else Path(settings.database_url.removeprefix('sqlite:///')).resolve().parent / 'zoho-connection.enc'
    return cipher, fingerprint, path


@contextmanager
def locked(settings):
    """OS lock covers reads, writes and token refresh across processes/reloads."""
    cipher, fingerprint, path = configuration(settings)
    if path is None:
        with zoho_storage.locked(settings, cipher, fingerprint) as record:
            yield record
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + '.lock', 'a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0')
            lock.flush()
        deadline = time.monotonic() + 12
        while True:
            try:
                lock.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise HTTPException(409, 'Another connection operation is running. Try again shortly.') from None
                time.sleep(.05)
        try:
            try:
                record = json.loads(cipher.decrypt(path.read_bytes())) if path.exists() else {'binding': fingerprint}
            except (InvalidToken, ValueError, OSError):
                raise HTTPException(503, 'Cannot open the saved Zoho connection. Restore its encryption key or contact IT.') from None
            if record.get('binding') != fingerprint:
                raise HTTPException(409, 'Saved connection belongs to a different Finance database or client configuration.')
            # Persist even when a provider request fails: a consumed state must stay consumed.
            try:
                yield record
            finally:
                content = cipher.encrypt(json.dumps(record, separators=(',', ':')).encode())
                fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.zoho-')
                try:
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(content)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.chmod(temporary, 0o600)
                    os.replace(temporary, path)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
        finally:
            lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_UN)


def require_network(settings):
    if not settings.zoho_network_enabled:
        raise HTTPException(409,'Local testing uses saved records only. Zoho network requests are disabled in this environment.')


def start(settings, actor, session, outbound=False):
    require_network(settings)
    if outbound and settings.data_environment != 'official':
        raise HTTPException(409,'Bill/payment sending can only be authorised in official Finance, not the local test environment.')
    scopes = OUTBOUND_SCOPES if outbound else SCOPES
    with locked(settings) as record:
        now = time.time()
        pending = {key: value for key, value in record.get('pending', {}).items() if value['until'] > now}
        # One active attempt per initiating session; bounded storage.
        pending = {key: value for key, value in pending.items() if value['session'] != session}
        if len(pending) >= 20:
            raise HTTPException(429, 'Too many connection attempts. Wait a few minutes.')
        state = secrets.token_urlsafe(32)
        pending[hashlib.sha256(state.encode()).hexdigest()] = {'actor': actor, 'session': session, 'until': now + 300,'scopes':list(scopes)}
        record['pending'] = pending
    return {'url': REGIONS[settings.zoho_region][0] + '/oauth/v2/auth?' + urlencode({
        'scope': ','.join(scopes), 'client_id': settings.zoho_client_id.get_secret_value(),
        'redirect_uri': settings.zoho_redirect_uri, 'response_type': 'code',
        'access_type': 'offline', 'prompt': 'consent', 'state': state})}


def token_request(settings, body, expected_scopes=SCOPES):
    require_network(settings)
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            response = client.post(REGIONS[settings.zoho_region][0] + '/oauth/v2/token', data={
                'client_id': settings.zoho_client_id.get_secret_value(),
                'client_secret': settings.zoho_client_secret.get_secret_value(), **body})
        result = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, 'Zoho could not complete authorisation. Start a new connection attempt.') from None
    if response.status_code == 429:
        raise HTTPException(429, 'Zoho is limiting requests. Wait before trying again.')
    if response.status_code >= 400 or not isinstance(result, dict) or not result.get('access_token'):
        raise HTTPException(409, 'Zoho authorisation expired or was refused. Reconnect to continue.')
    if result.get('api_domain', REGIONS[settings.zoho_region][1]) != REGIONS[settings.zoho_region][1]:
        raise HTTPException(409, 'Zoho returned another data centre. Check the configured region before reconnecting.')
    if result.get('scope'):
        scopes = set(result['scope'].replace(',', ' ').split())
        if scopes != set(expected_scopes):
            raise HTTPException(409, 'Zoho returned different permissions. Reconnect with the requested read access.')
    return result


def complete(settings, actor, session, state, code, error):
    with locked(settings) as record:
        key = hashlib.sha256(state.encode()).hexdigest()
        pending = record.get('pending', {}).get(key)
        if not pending or pending['actor'] != actor or pending['session'] != session or pending['until'] <= time.time():
            raise HTTPException(400, 'This connection attempt expired or belongs to another session. Start again.')
        del record['pending'][key]
        if error or not code:
            raise HTTPException(400, 'Zoho access was not granted. No connection was changed.')
        granted=pending.get('scopes',list(SCOPES))
        tokens = token_request(settings, {'grant_type': 'authorization_code', 'code': code,
                                         'redirect_uri': settings.zoho_redirect_uri},granted)
        if not tokens.get('refresh_token'):
            raise HTTPException(409, 'Zoho did not return offline access. Reconnect and grant consent again.')
        record['connection'] = {'access': tokens['access_token'], 'refresh': tokens['refresh_token'],
                                'expires': time.time() + min(int(tokens.get('expires_in', 3600)), 3600),
                                'connectedBy': actor, 'connectedAt': time.time(), 'organization': None,'scopes':granted}
    return {'ok': True}


def refresh(settings, connection):
    result = token_request(settings, {'grant_type': 'refresh_token', 'refresh_token': connection['refresh']},connection.get('scopes',SCOPES))
    connection['access'] = result['access_token']
    connection['expires'] = time.time() + min(int(result.get('expires_in', 3600)), 3600)
    if result.get('refresh_token'):
        connection['refresh'] = result['refresh_token']


def organizations(settings, record):
    require_network(settings)
    connection = record.get('connection')
    if not connection:
        raise HTTPException(409, 'Connect to Zoho first.')
    if connection['expires'] <= time.time() + 60:
        refresh(settings, connection)
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            def get():
                return client.get(REGIONS[settings.zoho_region][1] + '/books/v3/organizations',
                                  headers={'Authorization': 'Zoho-oauthtoken ' + connection['access']})
            response = get()
            if response.status_code == 401:
                refresh(settings, connection)
                response = get()
        result = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, 'Cannot check Zoho right now. Your saved connection is unchanged.') from None
    if response.status_code == 429:
        raise HTTPException(429, 'Zoho is limiting requests. Try again later.')
    if response.status_code >= 400 or not isinstance(result, dict) or result.get('code') != 0:
        raise HTTPException(409, 'Zoho refused the organisation check. Check access or reconnect.')
    rows = result.get('organizations', [])
    return [{'id': str(row['organization_id']), 'name': str(row.get('name', 'Unnamed organisation')),
             'currency': str(row.get('currency_code', ''))} for row in rows if row.get('organization_id')]


def saved_record(settings):
    """Read state without the refresh lock or any provider request."""
    cipher, binding, path = configuration(settings)
    if path is None:
        return zoho_storage.snapshot(settings, cipher, binding)
    try:
        return zoho_storage.decode(cipher, path.read_text(encoding='ascii'), binding)
    except OSError:
        return {'binding': binding}


def status(settings):
    try:
        configuration(settings)
    except HTTPException as error:
        return {'configured': False, 'authorized': False, 'organization': None, 'message': error.detail,
                'scopes': list(SCOPES), 'localOnly': True}
    record = saved_record(settings)
    connection = record.get('connection', {})
    database = zoho_storage.database_mode(settings)
    return {'configured': True, 'authorized': bool(connection), 'organization': connection.get('organization'),
                'message': ('Read-only connection authorised for the selected organisation. Source sync runs separately; view Sales orders and Zoho invoices for saved coverage.'
                            if connection.get('organization') else 'Connection authorised. Confirm the organisation before any future sync.')
                           if connection else 'Ready to connect.',
                'scopes': list(connection.get('scopes',SCOPES)), 'localOnly': not database,
                'storage': 'Encrypted database storage' if database else 'Encrypted local connection storage',
                'workerEnabled': settings.zoho_worker_enabled if database else settings.zoho_network_enabled,
                'networkEnabled':settings.zoho_network_enabled,
                'outboundAuthorized':set(OUTBOUND_SCOPES)<=set(connection.get('scopes',SCOPES)),
                'outboundEnabled':settings.zoho_outbound_enabled}
