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
