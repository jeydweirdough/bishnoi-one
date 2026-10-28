"""Short database transactions coordinate workers, pause state and request budgets."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import uuid
from fastapi import HTTPException
from sqlalchemy import select, text, func
from sqlalchemy.exc import SQLAlchemyError
from app.models import ZohoRuntime
from app.zoho_storage import factory

owner_context = ContextVar('finance_zoho_worker', default=None)
LEASE_SECONDS = 120


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


@contextmanager
def row(settings, organization):
    try:
        with factory(settings)() as db:
            if db.bind.dialect.name == 'postgresql':
                from sqlalchemy.dialects.postgresql import insert
                db.execute(text("SET LOCAL lock_timeout = '10s'"))
            else:
                from sqlalchemy.dialects.sqlite import insert
                db.execute(text('BEGIN IMMEDIATE'))
            now = aware(db.scalar(select(func.now())))
            db.execute(insert(ZohoRuntime).values(connection_id=settings.zoho_connection_id,
                organization_id=organization, paused=False, requests=0, updated_at=now)
                .on_conflict_do_nothing(index_elements=['connection_id', 'organization_id']))
            state = db.scalar(select(ZohoRuntime).where(ZohoRuntime.connection_id == settings.zoho_connection_id,
                ZohoRuntime.organization_id == organization).with_for_update())
            yield state, now
            state.updated_at = now
            db.commit()
    except SQLAlchemyError:
        raise HTTPException(503, 'The Zoho updater control is busy or unavailable. Saved records remain available.') from None


def owns(state, now):
    active = owner_context.get()
    return bool(active and active == (state.connection_id, state.organization_id, state.owner)
                and state.lease_until and aware(state.lease_until) > now and not state.paused)


@contextmanager
def worker(settings, organization):
    if not settings.zoho_worker_enabled:
        raise HTTPException(409, 'The PostgreSQL updater is not enabled. IT must enable one worker after the reviewed switch.')
    owner = uuid.uuid4().hex
    with row(settings, organization) as (state, now):
        if state.paused:
            raise HTTPException(409, 'The Zoho updater is paused.')
        if state.owner and state.lease_until and aware(state.lease_until) > now:
            raise HTTPException(409, 'Another Zoho updater is already running.')
        state.owner, state.lease_until = owner, now + timedelta(seconds=LEASE_SECONDS)
    token = owner_context.set((settings.zoho_connection_id, organization, owner))
    try:
        yield
    finally:
        owner_context.reset(token)
        with row(settings, organization) as (state, now):
            if state.owner == owner:
                state.owner, state.lease_until = None, None


def reserve(settings, organization, limit):
    if not 1 <= limit <= 1000:
        raise HTTPException(422, 'Choose a daily Zoho request limit from 1 to 1000.')
    with row(settings, organization) as (state, now):
        if not owns(state, now):
            raise HTTPException(409, 'The Zoho updater stopped or lost ownership. Start a fresh run.')
        day = now.astimezone(ZoneInfo('Asia/Manila')).date()
        if state.quota_day != day:
            state.quota_day, state.requests = day, 0
        if state.requests >= limit:
            raise HTTPException(429, 'Finance reached its daily Zoho read limit. Saved records remain available.')
        state.requests += 1  # Reserve before sending; a failed or retried GET still counts.
        state.lease_until = now + timedelta(seconds=LEASE_SECONDS)


@contextmanager
def fence(settings, organization):
    with row(settings, organization) as (state, now):
        if not owns(state, now):
            raise HTTPException(409, 'Updater ownership changed; this old result was not saved.')
        state.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        yield


def pause(settings, organization, paused):
    with row(settings, organization) as (state, now):
        state.paused = paused
        if paused:
            state.owner, state.lease_until = None, None


def status(settings, organization):
    with factory(settings)() as db:
        state = db.get(ZohoRuntime, (settings.zoho_connection_id, organization))
        now = aware(db.scalar(select(func.now())))
        if not state:
            return {'state': 'not-started', 'requestsToday': 0}
        day = now.astimezone(ZoneInfo('Asia/Manila')).date()
        return {'state': 'paused' if state.paused else 'running' if state.owner and state.lease_until
                and aware(state.lease_until) > now else 'idle',
                'requestsToday': state.requests if state.quota_day == day else 0,
                'checkedAt': now.isoformat()}
