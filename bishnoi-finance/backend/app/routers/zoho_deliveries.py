"""Administrator review of asynchronous delivery; never sends from a request."""
from collections import Counter
from typing import Literal
from fastapi import APIRouter,HTTPException,Query
from sqlalchemy import select,func
from pydantic import Field
from app.access import permitted
from app.deps import DB,SettingsDep
from app.routers.tax import Api
from app.models import ZohoDelivery,ZohoDeliveryEvent,ZohoLink,utcnow
from app.zoho_outbox import LABELS,REASONS,event
from app.audit import audit

router=APIRouter(prefix='/finance/integrations/zoho/deliveries',tags=['Zoho deliveries'])


@router.get('')
def listing(user:permitted('integrations.manage'),db:DB,settings:SettingsDep,state:str=Query('',max_length=30),page:int=Query(1,ge=1)):
    base=ZohoDelivery.environment==settings.data_environment
    counts=dict(db.execute(select(ZohoDelivery.status,func.count()).where(base).group_by(ZohoDelivery.status)).all())
    query=select(ZohoDelivery).where(base)
    if state:query=query.where(ZohoDelivery.status==state)
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    rows=list(db.scalars(query.order_by(ZohoDelivery.created_at).offset((page-1)*25).limit(25)))
    oldest=db.scalar(select(func.min(ZohoDelivery.created_at)).where(base,ZohoDelivery.status.not_in(['sent','cancelled'])))
    return {'counts':counts,'total':total,'page':page,'pageSize':25,'liveSendingEnabled':settings.zoho_outbound_enabled,
        'items':[{'id':r.id,'kind':r.kind,'localId':r.local_id,'number':r.snapshot.get('number'),
            'status':r.status,'label':LABELS.get(r.status,'Needs attention'),'message':REASONS.get(r.error_code),
            'attempts':r.attempts,'createdAt':r.created_at.isoformat(),'updatedAt':r.updated_at.isoformat(),
            'nextAttempt':r.next_attempt.isoformat(),'remoteId':r.remote_id} for r in rows],
        'oldestWaitingAt':oldest.isoformat() if oldest else None}


class Retry(Api):
    reason:str=Field(min_length=3,max_length=300)


@router.post('/{delivery_id}/retry')
def retry(delivery_id:str,body:Retry,user:permitted('integrations.manage'),db:DB,settings:SettingsDep):
    row=db.get(ZohoDelivery,delivery_id)
    if not row or row.environment!=settings.data_environment:raise HTTPException(404,'Delivery not found.')
    if row.status not in ('waiting_for_setup','waiting_for_bill','needs_attention') or row.attempts or row.remote_id:
        raise HTTPException(409,'This job may already exist in Zoho. Reconcile it before any new send; it was not retried.')
    if not row.organization_id:
        from app.zoho_connection import saved_record
        selected=(saved_record(settings).get('connection') or {}).get('organization')
        if not selected:raise HTTPException(409,'Connect and confirm the organisation first.')
        row.organization_id=selected['id']
    row.status='waiting_to_send';row.next_attempt=utcnow();row.error_code=None
    event(db,row,'retry_requested',user.full_name)
    audit(db,user,'zoho.delivery_retry',target_type='zoho_delivery',target_id=row.id,fields=['reason'])
    db.commit();return {'ok':True}


class Mapping(Api):
    kind:Literal['supplier','account','money_account','vat','withholding','company','bill']
    local_id:str=Field(min_length=1,max_length=80)
    remote_id:str|None=Field(None,pattern=r'^[A-Za-z0-9_-]{1,80}$')
    field_id:str|None=Field(None,pattern=r'^[A-Za-z0-9_-]{1,80}$')
    company_value:str|None=Field(None,max_length=120)
    confirmed_no_tax:bool=False
    confirm:bool=False


@router.post('/mappings')
def mapping(body:Mapping,user:permitted('integrations.manage'),db:DB,settings:SettingsDep):
    if not body.confirm:raise HTTPException(422,'Confirm the mapping with Finance before saving it.')
    from app.zoho_connection import saved_record
    selected=(saved_record(settings).get('connection') or {}).get('organization')
    if not selected:raise HTTPException(409,'Connect and confirm the organisation first.')
    if body.kind=='company' and (body.local_id!='2mg' or not body.field_id or not body.company_value):raise HTTPException(422,'Supply the confirmed 2MG bill-company field and value.')
    if body.kind not in ('company','vat') and not body.remote_id:raise HTTPException(422,'Supply the verified Zoho record ID.')
    if body.kind=='vat' and not body.remote_id and not body.confirmed_no_tax:raise HTTPException(422,'Choose a Zoho tax or confirm no tax.')
    key=(selected['id'],body.kind,body.local_id);row=db.get(ZohoLink,key)
    if row and row.remote_id and row.remote_id!=body.remote_id:
        raise HTTPException(409,'An existing link points to another Zoho record. Review it before changing identities.')
    if not row:row=ZohoLink(organization_id=key[0],kind=key[1],local_id=key[2],confirmed_by=user.full_name);db.add(row)
    row.remote_id=body.remote_id;row.confirmed=True;row.updated_at=utcnow();row.confirmed_by=user.full_name
    row.details={'fieldId':body.field_id,'value':body.company_value,'confirmedNoTax':body.confirmed_no_tax}
    audit(db,user,'zoho.mapping_confirmed',target_type='zoho_mapping',fields=['remote_id','details'])
    db.commit();return {'ok':True}
