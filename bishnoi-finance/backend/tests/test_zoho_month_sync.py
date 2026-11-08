from datetime import datetime,timezone
import pytest
from sqlalchemy import select,func
from app.zoho_month_sync import sync_month,save_document
from app.zoho_probe import ProbeStopped
from app.models import ZohoSourceDocument,Invoice,JournalEntry
from .test_tax_api import app,client,ana,ben  # noqa:F401
from .test_zoho_source import inv,order,staged,coverage
from .test_zoho_connection import configured,connect  # noqa:F401
from app.zoho_source import persist
from app import zoho_connection as oauth

class Reader:
    organization='org';calls=0;refreshes=0
    def __init__(self,data,limit=100):self.data=data;self.limit=limit;self.calls=0;self.params=[]
    def get(self,path,params=None):
        if self.calls>=self.limit:raise ProbeStopped('Budget reached')
        self.calls+=1;self.params.append((path,params))
        return self.data[(path,params['page'])] if params else self.data[path]

def summary(id,kind='invoice'):
    raw=inv(id,'INV-'+id,'2mg Incorporated',[]) if kind=='invoice' else order(id,[])
    raw['date']='2026-10-15';raw['last_modified_time']='2026-10-27T12:00:00+0800';raw.pop('line_items',None)
    return raw


def test_summary_scan_resumes_without_skipping_and_then_incremental(app):
    data={('/invoices',1):{'invoices':[summary('a')],'page_context':{'has_more_page':True}},
          ('/invoices',2):{'invoices':[summary('b')],'page_context':{'has_more_page':False}},
          ('/salesorders',1):{'salesorders':[summary('one','salesorder')],'page_context':{'has_more_page':False}}}
    first=sync_month(app.state.sessions,Reader(data,2),'2026-10-01','2026-10-27',detail_limit=0)
    assert not first['summaryComplete'] and first['cursors']=={'invoice':None,'salesorder':1}
    second_reader=Reader(data)
    second=sync_month(app.state.sessions,second_reader,'2026-10-01','2026-10-27',detail_limit=0)
    assert second['summaryComplete'] and second['savedMonthOrders']==1 and second['savedMonthInvoices']==2
    assert second_reader.calls==1 and second['checkpoint']==first['targetCheckpoint']
    third_reader=Reader(data)
    third=sync_month(app.state.sessions,third_reader,'2026-10-01','2026-10-27',detail_limit=0)
    assert third['summaryComplete'] and all('last_modified_time' in p for _,p in third_reader.params)
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ZohoSourceDocument))==3
        assert db.scalar(select(func.count()).select_from(Invoice))==0
        assert db.scalar(select(func.count()).select_from(JournalEntry))==0


def test_summary_does_not_claim_old_detail_is_fresh(app):
    raw=summary('a');raw['line_items']=[{'name':'Example','quantity':1,'rate':'1.25','item_total':'1.25'}]
    with app.state.sessions() as db:
        save_document(db,'org','invoice',raw,True);db.commit()
        same=dict(raw);same.pop('line_items')
        save_document(db,'org','invoice',same,False);db.commit()
        row=db.get(ZohoSourceDocument,('org','invoice','a'))
        assert row.data['detailLoaded'] and row.data['lines'][0]['name']=='Example'
        same['last_modified_time']='2026-10-27T13:00:00+0800';same['balance']='20.00'
        save_document(db,'org','invoice',same,False);db.commit()
        row=db.get(ZohoSourceDocument,('org','invoice','a'))
        assert not row.data['detailLoaded'] and not row.data['relationshipsFresh']
        assert row.data['balanceCentavos']==2000


def test_source_invoice_permissions_separation_and_readonly_org_file(client,ana,ben,app,configured,monkeypatch):
    from .test_dashboard import person
    none=person(client,ana,'No source invoice access',[])
    settings,_=configured;connect(client,ana)
    with oauth.locked(settings) as record:record['connection']['organization']={'id':'org','name':'Example'}
    with app.state.sessions() as db:persist(db,'org',staged(),coverage(),datetime.now(timezone.utc))
    # Page endpoints must not acquire the network/token lock or make Zoho calls.
    monkeypatch.setattr(oauth,'locked',lambda *args: (_ for _ in ()).throw(AssertionError('Page acquired network lock')))
    r=client.get('/finance/zoho-invoices?period=all',headers=ana)
    assert r.status_code==200 and r.json()['total']==2 and r.json()['savedCount']==4
    assert client.get('/finance/zoho-invoices?period=all&company=all',headers=ana).json()['total']==4
    assert client.get('/finance/zoho-invoices/a',headers=ana).json()['number']=='GPI-A'
    assert client.get('/finance/zoho-invoices',headers=none).status_code==403
    assert client.get('/finance/zoho-invoices',headers=ben).status_code==200  # Existing invoices.view grant.
    assert client.get('/finance/zoho-sales-orders?period=all',headers=ana).status_code==200
    assert client.post('/finance/zoho-invoices',headers=ana,json={}).status_code==405

def test_daily_self_cap_stops_before_another_provider_read(app):
    data={('/invoices',1):{'invoices':[summary('a')],'page_context':{'has_more_page':False}},
          ('/salesorders',1):{'salesorders':[],'page_context':{'has_more_page':False}}}
    reader=Reader(data)
    result=sync_month(app.state.sessions,reader,'2026-10-01','2026-10-27',detail_limit=0,daily_limit=1)
    assert reader.calls==1 and not result['summaryComplete'] and result['error']
    second=Reader(data)
    with pytest.raises(ProbeStopped):sync_month(app.state.sessions,second,'2026-10-01','2026-10-27',detail_limit=0,daily_limit=1)
    assert second.calls==0


# --- the request budget (Plan - Zoho reader budget, 2026-10-30) ---------------------------------------------
from zoneinfo import ZoneInfo
from math import ceil
from app.zoho_month_sync import backfill_allowance
from app.zoho_probe import ZohoLimit

MNL=ZoneInfo('Asia/Manila')
MONDAY_8=datetime(2026,10,26,8,0,tzinfo=MNL)
SATURDAY=datetime(2026,10,31,10,0,tzinfo=MNL)


def full(id,changed='2026-10-27T12:00:00+0800'):
    raw=inv(id,'INV-'+id,'2mg Incorporated',[]);raw['date']='2026-10-15';raw['last_modified_time']=changed
    return raw


def lists(invoices):
    return {('/invoices',1):{'invoices':invoices,'page_context':{'has_more_page':False}},
            ('/salesorders',1):{'salesorders':[],'page_context':{'has_more_page':False}}}


def test_backfill_is_spread_over_the_working_day_and_keeps_a_reserve():
    assert backfill_allowance(SATURDAY,0,500,300)[0]==0
    assert backfill_allowance(MONDAY_8.replace(hour=6),0,500,300)[0]==0
    assert backfill_allowance(MONDAY_8.replace(hour=16),0,500,300)[0]==0
    allowed,reserve,_=backfill_allowance(MONDAY_8,0,500,300)
    assert reserve==100 and allowed==ceil(400/96)  # 8 hours left = 96 five-minute cycles
    assert backfill_allowance(MONDAY_8.replace(hour=15,minute=56),390,500,300)[0]==10  # last cycle: what's spare
    assert backfill_allowance(MONDAY_8,400,500,300)[0]==0  # only the reserve is left


def test_changed_records_get_details_first_and_backfill_never_starves_them(app):
    sessions=app.state.sessions
    sync_month(sessions,Reader(lists([summary('a'),summary('b'),summary('c')])),'2026-10-01','2026-10-27',detail_limit=0,now=lambda:SATURDAY)
    with sessions() as db:  # First seen in the full list: backlog, not "changed".
        assert not any(r.data.get('changedAt') for r in db.scalars(select(ZohoSourceDocument)))
    newer=summary('b');newer['last_modified_time']='2026-10-28T09:00:00+0800'
    feed={**lists([newer,summary('d')]),'/invoices/b':{'invoice':full('b','2026-10-28T09:00:00+0800')},'/invoices/d':{'invoice':full('d')}}
    reader=Reader(feed)
    result=sync_month(sessions,reader,'2026-10-01','2026-10-27',detail_limit=5,now=lambda:SATURDAY)
    assert all('last_modified_time' in p for _,p in reader.params if p)  # change scan, not the full list
    assert result['changedDetailReads']==2 and result['backfillDetailReads']==0 and result['budget']['reason'].startswith('Weekend')
    assert result['changedPending']==0 and result['pendingDetails']==2
    backlog={**lists([]),'/invoices/a':{'invoice':full('a')},'/invoices/c':{'invoice':full('c')}}
    weekday=sync_month(sessions,Reader(backlog),'2026-10-01','2026-10-27',detail_limit=5,now=lambda:MONDAY_8)
    assert weekday['backfillDetailReads']==2 and weekday['pendingDetails']==0


def test_the_daily_cap_is_never_exceeded_even_by_changes(app):
    sessions=app.state.sessions
    sync_month(sessions,Reader(lists([])),'2026-10-01','2026-10-27',detail_limit=0)
    feed={**lists([summary(x) for x in 'pqrs']),**{f'/invoices/{x}':{'invoice':full(x)} for x in 'pqrs'}}
    reader=Reader(feed)
    result=sync_month(sessions,reader,'2026-10-01','2026-10-27',detail_limit=10,daily_limit=5,now=lambda:SATURDAY)
    assert reader.calls==3 and result['usedToday']==5 and result['error']  # 2 earlier + 2 lists + 1 detail


def test_zoho_daily_limit_stops_until_tomorrow_but_a_minute_limit_only_ends_the_cycle(app):
    sessions=app.state.sessions
    class Limited(Reader):
        def __init__(self,code):super().__init__(lists([]));self.code=code
        def get(self,path,params=None):self.calls+=1;raise ZohoLimit(self.code)
    minute=sync_month(sessions,Limited(44),'2026-10-01','2026-10-27',detail_limit=0)
    assert minute['zohoLimit']=='minute' and not minute['zohoDailyLimitHit'] and '100 requests' in minute['error']
    assert sync_month(sessions,Reader(lists([])),'2026-10-01','2026-10-27',detail_limit=0)['summaryComplete']
    day=sync_month(sessions,Limited(45),'2026-10-01','2026-10-27',detail_limit=0)
    assert day['zohoDailyLimitHit'] and 'until tomorrow' in day['error']
    later=Reader(lists([]))
    with pytest.raises(ProbeStopped):sync_month(sessions,later,'2026-10-01','2026-10-27',detail_limit=0)
    assert later.calls==0
    assert ZohoLimit(None).kind=='unknown' and ZohoLimit(1070).kind=='concurrent'


def test_daily_full_list_flags_saved_records_zoho_no_longer_lists(app):
    sessions=app.state.sessions
    with sessions() as db:save_document(db,'org','invoice',summary('gone'),False);db.commit()
    result=sync_month(sessions,Reader(lists([summary('a')])),'2026-10-01','2026-10-27',detail_limit=0)
    check=result['totalsCheck']
    assert check['listedInvoices']==1 and check['notListedByZoho']==1 and check['examples'][0]['id']=='gone'
    with sessions() as db:assert db.get(ZohoSourceDocument,('org','invoice','gone'))  # flagged, never deleted


def test_an_older_detail_never_overwrites_a_newer_summary(app):
    sessions=app.state.sessions
    sync_month(sessions,Reader(lists([])),'2026-10-01','2026-10-27',detail_limit=0)
    newer=summary('a');newer['last_modified_time']='2026-10-28T09:00:00+0800'
    feed={**lists([newer]),'/invoices/a':{'invoice':full('a','2026-10-27T12:00:00+0800')}}
    result=sync_month(sessions,Reader(feed),'2026-10-01','2026-10-27',detail_limit=2,now=lambda:SATURDAY)
    assert result['staleDetails']>=1 and result['changedPending']==1
