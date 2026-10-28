from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import select,func
from app import zoho_connection as oauth
from app.models import ZohoSourceDocument,SalesOrder,Invoice,JournalEntry,ZohoSourceRun
from app.zoho_source import normalize,persist,saved_orders,capture,money
from .test_tax_api import app,client,ana,ben  # noqa: F401
from .test_zoho_connection import configured,connect  # noqa: F401


def inv(id,number,company,orders,amount='1120.00'):
    return {'invoice_id':id,'invoice_number':number,'date':'2026-01-15','status':'sent',
            'customer_id':'fictional-customer','customer_name':'Example buyer','total':amount,'balance':amount,'currency_code':'PHP',
            'custom_fields':[{'api_name':'cf_invoicing_from','label':'Invoicing From','value':company}],
            'salesorders':[{'salesorder_id':i} for i in orders],
            'line_items':[{'line_item_id':'il-'+id,'salesorder_item_id':'ol-example','name':'Example item','quantity':1,'rate':'1000','item_total':'1000'}]}


def order(id,invoices):
    return {'salesorder_id':id,'salesorder_number':'SO-'+id,'date':'2026-01-14','status':'confirmed',
            'customer_name':'Example buyer','total':'2240.00','currency_code':'PHP',
            'invoices':[{'invoice_id':i} for i in invoices],
            'line_items':[{'line_item_id':'ol-example','name':'Example item','quantity':2,'rate':'1000','item_total':'2000'}]}


def staged():
    docs=[('invoice',inv('a','GPI-A','2mg Incorporated',['one'])),
          ('invoice',inv('b','2MG-B','Getmeds Philippines Inc.',['one'])),
          ('invoice',inv('c','INV-C','2mg Incorporated',['two'])),
          ('invoice',inv('d','2MG-D','Something else',['three'])),
          ('salesorder',order('one',['a','b'])),('salesorder',order('two',['c'])),('salesorder',order('three',['d']))]
    return {(kind,normalize(kind,raw)['id']):normalize(kind,raw) for kind,raw in docs}


def coverage():
    return {'windowStart':'2026-01-01','windowEnd':'2026-03-31','partial':True,'error':None,'orderDetails':3,'invoiceDetails':4}


def test_company_from_field_not_prefix_and_money_precision():
    docs=staged()
    assert docs['invoice','a']['company']=='2mg' and docs['invoice','b']['company']=='gpi'
    assert docs['invoice','c']['company']=='2mg' and docs['invoice','d']['company']=='unknown'
    assert money(Decimal('0.105'))==11 and money('1120.00')==112000
    with pytest.raises(ValueError):money('NaN')
    bad=inv('x','2MG-X','2MG',['one'])
    assert normalize('invoice',bad)['company']=='unknown'  # no unapproved substring aliases


def test_source_upsert_filters_org_isolation_no_financial_writes(client,ana,ben,app,configured):
    s,_=configured;connect(client,ana)
    with oauth.locked(s) as record:record['connection']['organization']={'id':'org-one','name':'Example','currency':'PHP'}
    with app.state.sessions() as db:
        for _ in range(2):persist(db,'org-one',staged(),coverage(),datetime.now(timezone.utc))
        persist(db,'other-org',{('salesorder','foreign'):normalize('salesorder',order('foreign',[]))},coverage(),datetime.now(timezone.utc))
        assert db.scalar(select(func.count()).select_from(ZohoSourceDocument).where(ZohoSourceDocument.organization_id=='org-one'))==7
        assert len(saved_orders(db,'org-one'))==3
        for model in (SalesOrder,Invoice,JournalEntry):assert db.scalar(select(func.count()).select_from(model))==0
    base='/finance/zoho-sales-orders'
    assert client.get(base,headers=ben).status_code==403
    two=client.get(base+'?period=all',headers=ana).json();assert two['total']==2 and two['savedCount']==3
    mixed=next(r for r in two['items'] if r['id']=='one');assert mixed['companyLabel']=='Mixed: 2MG and GPI'
    assert mixed['twoMgInvoiceTotals']==[{'currency':'PHP','centavos':112000}]
    assert len(mixed['invoices'])==2
    assert client.get(base+'?company=all&period=all',headers=ana).json()['total']==3
    assert client.get(base+'?company=all&period=all&q=INV-C',headers=ana).json()['total']==1
    assert client.get(base+'/foreign',headers=ana).status_code==404
    assert client.get(base+'/one',headers=ben).status_code==403
    assert client.put(base+'/one',headers=ana,json={}).status_code==405


def test_unread_and_conflicting_links_not_counted_as_two_mg(app):
    docs=staged();docs['salesorder','three']['invoiceIds']+=['missing','a']
    with app.state.sessions() as db:
        persist(db,'org',docs,coverage(),datetime.now(timezone.utc))
        row=next(r for r in saved_orders(db,'org') if r['id']=='three')
        assert row['missingInvoiceDetails']==1 and row['relationshipIssues']==1
        assert not row['has2mg'] and row['twoMgInvoiceTotals']==[]


def test_capture_bounded_complete_documents_and_field_allowlist():
    class Reader:
        calls=0
        def get(self,path,params=None):
            self.calls+=1
            if path=='/invoices':return {'invoices':[{'invoice_id':'a','invoice_number':'GPI-A','date':'2026-01-15'}],'page_context':{'has_more_page':False}}
            if path=='/invoices/a':
                data=inv('a','GPI-A','2mg Incorporated',['one']);data['bank_account_number']='DO NOT STORE';data['notes']='DO NOT STORE';return {'invoice':data}
            if path=='/salesorders/one':return {'salesorder':order('one',['a','not-read'])}
            raise AssertionError('Unexpected request')
    docs,result=capture(Reader(),'2026-01-01','2026-03-31',related_limit=0)
    assert len(docs)==2 and result['unreadLinkedInvoices']==1 and result['partial']
    assert 'DO NOT STORE' not in str(docs)
    assert docs['invoice','a']['lines'][0]['orderLineId']=='ol-example'
