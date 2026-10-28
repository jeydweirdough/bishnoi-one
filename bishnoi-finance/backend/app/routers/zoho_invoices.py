"""Permission-gated source invoice copies, independent of local accounting invoices."""
from typing import Literal
from fastapi import APIRouter,Query,HTTPException
from sqlalchemy import select,func
from app.access import permitted,access_of
from app.deps import DB,SettingsDep
from app.models import ZohoSourceDocument,Invoice
from app.routers.zoho_source import organization,dates,latest_coverage

router=APIRouter(prefix='/finance/zoho-invoices',tags=['Zoho source invoices'])

@router.get('')
def listing(user:permitted('invoices.view'),db:DB,settings:SettingsDep,
            company:Literal['2mg','all']='2mg',q:str=Query('',max_length=200),page:int=Query(1,ge=1),period:Literal['month','q1','all']='month'):
    org=organization(settings);start,end=dates(period)
    all_rows=[{**r.data,'fetchedAt':r.fetched_at.isoformat()} for r in db.scalars(select(ZohoSourceDocument).where(ZohoSourceDocument.organization_id==org,ZohoSourceDocument.kind=='invoice'))]
    if start:all_rows=[r for r in all_rows if start<=r['date']<=end]
    rows=[r for r in all_rows if company=='all' or r['company']=='2mg']
    if q.strip():
        needle=q.strip().casefold();rows=[r for r in rows if needle in ' '.join([r['number'],r['customerName'],r['reference']]).casefold()]
    rows.sort(key=lambda r:(r['date'],r['number'],r['id']),reverse=True)
    total=len(rows);page_size=20;page=min(page,max(1,(total+page_size-1)//page_size))
    return {'items':[{**r,'lines':[]} for r in rows[(page-1)*page_size:page*page_size]],'total':total,'page':page,'pageSize':page_size,
            'savedCount':len(all_rows),'twoMgCount':sum(r['company']=='2mg' for r in all_rows),
            'localCount':db.scalar(select(func.count()).select_from(Invoice)),
            'period':period,'windowStart':start,'windowEnd':end,'coverage':latest_coverage(db,org,start,end)}

@router.get('/{source_id}')
def detail(source_id:str,user:permitted('invoices.view'),db:DB,settings:SettingsDep):
    org=organization(settings);row=db.get(ZohoSourceDocument,(org,'invoice',source_id))
    if not row:raise HTTPException(404,'Saved Zoho invoice not found.')
    orders=[]
    if access_of(user).can('sales_orders.view'):
        for order_id in row.data['orderIds']:
            order=db.get(ZohoSourceDocument,(org,'salesorder',order_id))
            if order:orders.append({'id':order_id,'number':order.data['number']})
    return {**row.data,'fetchedAt':row.fetched_at.isoformat(),'orders':orders}
