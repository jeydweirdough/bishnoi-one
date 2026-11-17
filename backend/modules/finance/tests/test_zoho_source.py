from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import select,func
from modules.finance import zoho_connection as oauth
from modules.finance.models import ZohoSourceDocument,SalesOrder,Invoice,JournalEntry,ZohoSourceRun
from modules.finance.zoho_source import normalize,persist,capture,money
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


def test_source_upsert_filters_org_isolation_no_financial_writes(app):
    # The saved Zoho copies feed import review and the overview; the read-only Zoho lists were removed (2026-11-17).
    with app.state.sessions() as db:
        for _ in range(2):persist(db,'org-one',staged(),coverage(),datetime.now(timezone.utc))
        persist(db,'other-org',{('salesorder','foreign'):normalize('salesorder',order('foreign',[]))},coverage(),datetime.now(timezone.utc))
        assert db.scalar(select(func.count()).select_from(ZohoSourceDocument).where(ZohoSourceDocument.organization_id=='org-one'))==7
        assert db.scalar(select(func.count()).select_from(ZohoSourceDocument).where(ZohoSourceDocument.organization_id=='other-org'))==1
        for model in (SalesOrder,Invoice,JournalEntry):assert db.scalar(select(func.count()).select_from(model))==0


def test_the_read_only_zoho_lists_are_gone(client,ana):
    for path in ('/finance/zoho-sales-orders','/finance/zoho-sales-orders/one','/finance/zoho-invoices','/finance/zoho-invoices/a'):
        assert client.get(path,headers=ana).status_code==404


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
