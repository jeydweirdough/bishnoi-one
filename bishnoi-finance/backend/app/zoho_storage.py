"""Encrypted PostgreSQL OAuth state; never migrates, seeds, or calls Zoho."""
from contextlib import contextmanager
from functools import lru_cache
import json
from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from app.db import make_engine, make_sessions
from app.models import ZohoConnection, utcnow


def database_mode(settings):
    return not settings.database_url.startswith('sqlite:///')


@lru_cache(maxsize=8)
def sessions(address, driver):
    return make_sessions(make_engine(address, postgres_driver=driver))


def factory(settings):
    return sessions(settings.database_url, settings.postgres_driver)


def decode(cipher, encrypted, binding):
    try:
        record = json.loads(cipher.decrypt(encrypted.encode()))
    except (InvalidToken, ValueError, TypeError):
        raise HTTPException(503, 'Cannot open the saved Zoho connection. Restore its encryption key; nothing was overwritten.') from None
    if record.get('binding') != binding:
        raise HTTPException(409, 'Saved Zoho connection belongs to another environment or client. Reconnect in the intended environment.')
    return record


def snapshot(settings, cipher, binding):
    try:
        with factory(settings)() as db:
            row = db.get(ZohoConnection, settings.zoho_connection_id)
            return decode(cipher, row.encrypted, binding) if row else {'binding': binding}
    except SQLAlchemyError:
        raise HTTPException(503, 'Zoho connection storage is unavailable. Contact IT; saved data has not been changed.') from None


@contextmanager
def locked(settings, cipher, binding):
    try:
        with factory(settings)() as db:
            if db.bind.dialect.name == 'postgresql':
                db.execute(text("SET LOCAL lock_timeout = '10s'"))
                from sqlalchemy.dialects.postgresql import insert
            else:
                from sqlalchemy.dialects.sqlite import insert
                db.execute(text('BEGIN IMMEDIATE'))
            initial = cipher.encrypt(json.dumps({'binding': binding}).encode()).decode()
            db.execute(insert(ZohoConnection).values(id=settings.zoho_connection_id,
                encrypted=initial, revision=1, updated_at=utcnow()).on_conflict_do_nothing(index_elements=['id']))
            row = db.scalar(select(ZohoConnection).where(ZohoConnection.id == settings.zoho_connection_id).with_for_update())
            record = decode(cipher, row.encrypted, binding)
            # State consumption and successful refresh survive a later provider error.
            try:
                yield record
            finally:
                row.encrypted = cipher.encrypt(json.dumps(record, separators=(',', ':')).encode()).decode()
                row.revision += 1
                row.updated_at = utcnow()
                db.commit()
    except SQLAlchemyError:
        raise HTTPException(503, 'Zoho connection is busy or unavailable. Try again; no credentials are shown.') from None
