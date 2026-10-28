"""Review uploads transiently; actual posting rehearsal is local-only and isolated."""
from fastapi import APIRouter,HTTPException
from pydantic import Field
from typing import Literal
from sqlalchemy import select
from app.api import Api
from app.access import permitted,access_of
from app.deps import DB,SettingsDep
from app.models import Account,ZohoSourceDocument
from app.import_review import build,ReviewError
from app.money_accounts import money_account_ids

router=APIRouter(prefix='/finance/import-review',tags=['Import review'])

class File(Api):
    name:str=Field(min_length=1,max_length=200)
    content:str=Field(min_length=1,max_length=8*1024*1024)

class Pack(Api):
    files:list[File]=Field(min_length=1,max_length=20)
    choices:'Choices'=Field(default_factory=lambda:Choices())
    confirm:bool=False

class Choices(Api):
    accounts:dict[str,str]=Field(default_factory=dict,max_length=500)
    bill_companies:dict[str,Literal['2mg','gpi','unconfirmed']]=Field(default_factory=dict,max_length=500)
    expense_companies:dict[str,Literal['2mg','gpi','unconfirmed']]=Field(default_factory=dict,max_length=500)
    controls_company:Literal['unconfirmed','2mg']='unconfirmed'
    controls_currency:Literal['unconfirmed','PHP']='unconfirmed'
    confirm_control_references:bool=False

Pack.model_rebuild()

def inspect_pack(body,db,settings):
    money=money_account_ids(db);all_accounts=list(db.scalars(select(Account)))
    parents={a.parent_id for a in all_accounts if a.parent_id}
    accounts=[{'id':a.id,'code':a.code,'name':a.name,'type':a.type,'active':a.is_active,'posting':a.id not in parents,'money':a.id in money} for a in all_accounts]
    # Do not mix identities across organisations, or call Zoho to enrich an upload.
    from app.zoho_connection import saved_record
    try:org=((saved_record(settings).get('connection') or {}).get('organization') or {}).get('id')
    except HTTPException:org=None
    existing=set(db.execute(select(ZohoSourceDocument.kind,ZohoSourceDocument.source_id).where(ZohoSourceDocument.organization_id==org)).all()) if org else set()
    result=build([f.model_dump() for f in body.files],body.choices.model_dump(by_alias=True),accounts,existing)
    result['dataEnvironment']=settings.data_environment
    result['sourceComparison']={'available':bool(org),'message':'Matched only against saved IDs for the selected organisation.' if org else 'Saved Zoho comparison was not checked: no readable selected organisation. This result reviews the uploaded files only.'}
    return result

def check_access(user,result):
    can=access_of(user).can
    if not can('accounts.view'):raise HTTPException(403,'Import review needs View chart of accounts as well as Zoho connections access.')
    required={'invoice':'invoices.view','bill':'bills.view','customer_payment':'invoices.view','vendor_payment':'vouchers.view',
              'salesorder':'sales_orders.view','expense':'journal.view','ar':'invoices.view','ap':'bills.view'}
    if any(not can(required[f['kind']]) for f in result['files']):
        raise HTTPException(403,'Your role cannot review every record type in this pack. Ask the administrator for the relevant view permissions.')

@router.post('')
def review(body:Pack,user:permitted('integrations.manage'),db:DB,settings:SettingsDep):
    try:
        result=inspect_pack(body,db,settings);check_access(user,result);return result
    except ReviewError as error:raise HTTPException(422,str(error)) from None

@router.post('/rehearse')
def rehearse(body:Pack,user:permitted('integrations.manage'),db:DB,settings:SettingsDep):
    if settings.data_environment!='local_test' or not settings.database_url.startswith('sqlite:///'):
        raise HTTPException(409,'Run a posting rehearsal from the separate local testing site. Official records were not changed.')
    if not body.confirm:raise HTTPException(422,'Confirm creation of a separate private local rehearsal database.')
    if not access_of(user).can('journal.post'):raise HTTPException(403,'Local accounting rehearsal requires permission to post journal entries.')
    try:
        result=inspect_pack(body,db,settings)
        check_access(user,result)
        from app.import_rehearsal import rehearsal
        return rehearsal(result,db,user.full_name)
    except ReviewError as error:raise HTTPException(422,str(error)) from None
