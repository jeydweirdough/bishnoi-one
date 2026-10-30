"""Setup and organisation checks only; no Zoho business writes or transaction imports."""
from fastapi import APIRouter
from pydantic import Field
from app.access import permitted
from app.deps import SettingsDep, CurrentSession, DB
from app.routers.tax import Api
from app.audit import audit
from app import zoho_connection as connection

router = APIRouter(prefix='/finance/integrations/zoho', tags=['Finance connections'])

class Callback(Api):
    state: str = Field(min_length=1, max_length=200)
    code: str | None = Field(None, max_length=4096)
    error: str | None = Field(None, max_length=200)

class Organization(Api):
    organization_id: str = Field(min_length=1, max_length=80)

@router.get('')
def status(user: permitted('integrations.manage'), settings: SettingsDep, db: DB):
    result=connection.status(settings)
    selected=result.get('organization')
    result['sourceSync']={'state':'not-connected','lastAttempt':None,'lastCompletedScan':None}
    if selected:
        from sqlalchemy import select
        from app.models import ZohoSourceRun
        runs=list(db.scalars(select(ZohoSourceRun).where(ZohoSourceRun.organization_id==selected['id'])
            .order_by(ZohoSourceRun.started_at.desc()).limit(30)))
        latest=runs[0] if runs else None
        completed=next((r for r in runs if r.coverage.get('summaryComplete') and not r.coverage.get('error')),None)
        from app.zoho_month_sync import usage_today,zoho_day_limit_hit
        c=latest.coverage if latest else {}
        result['sourceSync']={'state':'needs-attention' if latest and c.get('error') else 'saved' if latest else 'not-started',
            'lastAttempt':latest.finished_at.isoformat() if latest else None,
            'lastCompletedScan':completed.finished_at.isoformat() if completed else None,
            'pendingDetails':c.get('pendingDetails') if latest else None,
            # The request budget (Plan - Zoho reader budget): today's use against the cap, what's kept for changes,
            # and what the last cycle spent on the older backlog and why.
            'usedToday':usage_today(db,selected['id']),'dailyLimit':c.get('dailyLimit'),'budget':c.get('budget'),
            'changedPending':c.get('changedPending'),'intervalSeconds':c.get('intervalSeconds'),'workHours':c.get('workHours'),
            'stoppedForToday':zoho_day_limit_hit(db,selected['id']),'error':c.get('error'),'totalsCheck':c.get('totalsCheck')}
        if not result.get('localOnly',True):
            from app.zoho_runtime import status as worker_status
            result['worker']=worker_status(settings,selected['id'])
    return result


class UpdaterControl(Api):
    paused: bool


@router.post('/updater')
def control_updater(body: UpdaterControl, user: permitted('integrations.manage'), settings: SettingsDep, db: DB):
    from fastapi import HTTPException
    from app.zoho_storage import database_mode
    from app.zoho_runtime import pause
    if not database_mode(settings):
        raise HTTPException(409,'This local updater is controlled by its PowerShell process. No local files were changed.')
    with connection.locked(settings) as record:
        selected=(record.get('connection') or {}).get('organization')
        if not selected:raise HTTPException(409,'Connect and confirm the Zoho organisation first.')
        pause(settings,selected['id'],body.paused)
    audit(db,user,'zoho.updater_paused' if body.paused else 'zoho.updater_resumed',target_type='connection',target='Zoho source updater')
    db.commit()
    return {'ok':True}

@router.post('/start')
def start(user: permitted('integrations.manage'), session: CurrentSession, settings: SettingsDep, outbound: bool=False):
    return connection.start(settings, user.id, session.id,outbound)

@router.post('/callback')
def callback(body: Callback, user: permitted('integrations.manage'), session: CurrentSession, settings: SettingsDep, db: DB):
    result = connection.complete(settings, user.id, session.id, body.state, body.code, body.error)
    audit(db, user, 'zoho.authorized', target_type='connection', target='Zoho read-only connection')
    db.commit()
    return result

@router.post('/check')
def check(user: permitted('integrations.manage'), settings: SettingsDep):
    with connection.locked(settings) as record:
        return {'organizations': connection.organizations(settings, record)}

@router.post('/organization')
def select_organization(body: Organization, user: permitted('integrations.manage'), settings: SettingsDep, db: DB):
    from fastapi import HTTPException
    with connection.locked(settings) as record:
        options = connection.organizations(settings, record)
        selected = next((row for row in options if row['id'] == body.organization_id), None)
        if not selected:
            raise HTTPException(422, 'Choose an organisation available to this connection.')
        record['connection']['organization'] = selected
    audit(db, user, 'zoho.organization_selected', target_type='connection', target='Zoho connection')
    db.commit()
    return {'ok': True}

@router.post('/disconnect')
def disconnect(user: permitted('integrations.manage'), settings: SettingsDep, db: DB):
    with connection.locked(settings) as record:
        from app.zoho_storage import database_mode
        if database_mode(settings) and (record.get('connection') or {}).get('organization'):
            from app.zoho_runtime import pause
            pause(settings,record['connection']['organization']['id'],True)
        record.pop('connection', None)
        record['pending'] = {}
    audit(db, user, 'zoho.disconnected_locally', target_type='connection', target='Zoho connection')
    db.commit()
    return {'ok': True}
