"""Local reads only. Zoho is contacted by the seed/sync tool, never by these screens."""
from typing import Literal
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func
from app.access import permitted
from app.deps import DB, SettingsDep
from app.models import SalesOrder, ZohoSourceRun
from app import zoho_connection as oauth
from app.zoho_source import saved_orders
from app.zoho_month_sync import month_window

router=APIRouter(prefix='/finance/zoho-sales-orders',tags=['Zoho source sales orders'])

def dates(period):
    return month_window() if period=='month' else ('2026-01-01','2026-03-31') if period=='q1' else (None,None)

def latest_coverage(db,org,start,end):
    stmt=select(ZohoSourceRun).where(ZohoSourceRun.organization_id==org)
    if start:stmt=stmt.where(ZohoSourceRun.window_start>=date.fromisoformat(start),ZohoSourceRun.window_start<=date.fromisoformat(end))
    run=db.scalar(stmt.order_by(ZohoSourceRun.finished_at.desc()))
    return {**run.coverage,'finishedAt':run.finished_at.isoformat()} if run else None


def organization(settings):
    # Atomic encrypted-file replacement allows a local read without waiting behind
    # the token-refresh/network lock. Page requests never wait for Zoho HTTP.
    record=oauth.saved_record(settings)
    selected=(record.get('connection') or {}).get('organization')
    if not selected:raise HTTPException(409,'Confirm the Zoho organisation on the connection page first.')
    return selected['id']


@router.get('')
def listing(user:permitted('sales_orders.view'),db:DB,settings:SettingsDep,
            company:Literal['2mg','all']='2mg',q:str=Query('',max_length=200),page:int=Query(1,ge=1),period:Literal['month','q1','all']='month'):
    org=organization(settings)
    all_rows=saved_orders(db,org)
    start,end=dates(period)
    if start:all_rows=[r for r in all_rows if start<=r['date']<=end]
    rows=[r for r in all_rows if company=='all' or r['has2mg']]
    if q.strip():
        needle=q.strip().casefold()
        rows=[r for r in rows if needle in ' '.join([r['number'],r['customerName'],r['reference'],*(i['number'] for i in r['invoices'])]).casefold()]
    total=len(rows);page_size=20;page=min(page,max(1,(total+page_size-1)//page_size))
    return {'items':rows[(page-1)*page_size:page*page_size],'total':total,'page':page,'pageSize':page_size,
            'savedCount':len(all_rows),'twoMgCount':sum(r['has2mg'] for r in all_rows),
            'localCount':db.scalar(select(func.count()).select_from(SalesOrder)),
            'period':period,'windowStart':start,'windowEnd':end,'coverage':latest_coverage(db,org,start,end)}


@router.get('/{source_id}')
def detail(source_id:str,user:permitted('sales_orders.view'),db:DB,settings:SettingsDep):
    order=next((r for r in saved_orders(db,organization(settings)) if r['id']==source_id),None)
    if not order: raise HTTPException(404,'Saved Zoho sales order not found.')
    return order
