"""Synthetic CSVs only; all real-record rehearsals live in separate local databases."""
import csv,io,json
from collections import Counter
from pathlib import Path
import pytest
from sqlalchemy import select,func
from app.import_review import parse,build,ReviewError,key
from app.models import Account,Invoice,Bill,JournalEntry
from .test_tax_api import app,client,ana,ben

def file(name,rows):
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return {'name':name,'content':stream.getvalue()}

def pack():
    invoice={'Invoice ID':'i1','Invoice Date':'2026-01-05','Invoice Number':'SOURCE-1','Customer ID':'c1','Customer Name':'Synthetic clinic',
        'Invoice Status':'Overdue','Currency Code':'PHP','CF.Invoicing From':'2mg Incorporated','SubTotal':'100.00','Total':'112.00',
        'Due Date':'2026-02-05','Account':'Source sales','Account Code':'Z-sales','Accounts Receivable':'Source AR','CF.TIN Number':'123456789',
        'Item Name':'Synthetic item','Item Total':'100.00','Item Tax Amount':'12.00','Item Tax':'VAT','Item Tax %':'12.00'}
    bill={'Bill ID':'b1','Bill Date':'2026-01-06','Bill Number':'SOURCE-B1','Vendor Name':'Synthetic supplier','Bill Status':'Overdue',
        'Currency Code':'PHP','CF.Company':'2MG','SubTotal':'50.00','Total':'56.00','Due Date':'2026-02-06',
        'Account':'Source expense','Account Code':'Z-cost','Accounts Payable':'Source AP','Item Name':'Synthetic cost','Item Total':'50.00','Tax Amount':'6.00','Tax Name':'VAT','Tax Percentage':'12.00'}
    received={'CustomerPayment ID':'p1','Date':'2026-02-02','Payment Number':'P-1','CustomerID':'c1','Customer Name':'Synthetic clinic','Payment Status':'Paid',
        'Currency Code':'PHP','Amount':'56.00','Unused Amount':'0.00','Bank Charges':'0.00','InvoicePayment ID':'a1','Mode':'Bank Transfer',
        'Invoice Number':'SOURCE-1','Invoice Date':'2026-01-05','Invoice Payment Applied Date':'2026-02-02',
        'Amount Applied to Invoice':'56.00','Withholding Tax Amount':'0.00','Deposit To':'Source bank','Deposit To Account Code':'Z-bank'}
    paid={'VendorPayment ID':'v1','Date':'2026-02-03','Payment Number':'V-1','Vendor Name':'Synthetic supplier','Payment Status':'Paid',
        'Currency Code':'PHP','Amount':'28.00','Unused Amount':'0.00','Bank Charges':'0.00','PIPayment ID':'va1','Bill ID':'b1','Bill Number':'SOURCE-B1','Mode':'Bank Transfer',
        'Bill Date':'2026-01-06','Bill Payment Applied Date':'2026-02-03','Bill Amount':'28.00','Withholding Tax Amount':'0.00','Paid Through':'Source bank','Paid Through Account Code':'Z-bank'}
    return [file('invoices.csv',[invoice]),file('bills.csv',[bill]),file('received.csv',[received]),file('paid.csv',[paid])]

def control(asof='December 31, 2025',amount='10.00'):
    rows=[['TAXPAYER TRADE NAME','Synthetic company'],['Date:',asof],[],['Customer','Reference','Transaction Date','Due Date','Current','1 to 30 Days','31 to 60 Days','Over 60 Days','Balance'],
        ['Synthetic old clinic','OLD-1','12/01/2025','12/31/2025',amount,'0.00','0.00','0.00',amount]]
    out=io.StringIO();csv.writer(out).writerows(rows);return {'name':'aging.csv','content':out.getvalue()}

def seed_choices(client,ana):
    data=client.post('/finance/import-review',headers=ana,json={'files':pack(),'choices':{'billCompanies':{'2MG':'2mg'}}}).json()
    accounts=client.get('/finance/ledger/accounts',headers=ana).json()['items']
    by_code={a['code']:a['id'] for a in accounts}
    # These are explicit synthetic test choices, not guesses against the supplied company files.
    for_code={'income':'4000','cost':'6500','money':'1010'}
    candidates={a['id']:a for a in data['accounts']}
    choices={'accounts':{},'billCompanies':{'2MG':'2mg'}}
    for group in data['accountGroups']:
        code=for_code.get(group['role'])
        if code:identity=by_code[code]
        else:
            t='asset' if group['role'] in ('receivable','input_tax') else 'liability'
            identity=next(a['id'] for a in data['accounts'] if a['type']==t and a['posting'] and not a['money'])
        choices['accounts'][group['id']]=identity
    return choices

def test_vendor_payment_is_not_misclassified_as_bill():
    docs,_,_=parse(pack())
    assert Counter(d['kind'] for d in docs)=={'invoice':1,'bill':1,'customer_payment':1,'vendor_payment':1}

def test_review_is_read_only_and_groups_links_without_auto_account_selection(app,client,ana,ben):
    with app.state.sessions() as db:before={t:db.scalar(select(func.count()).select_from(t)) for t in (Invoice,Bill,JournalEntry)}
    r=client.post('/finance/import-review',headers=ana,json={'files':pack()});assert r.status_code==200,r.text
    data=r.json();assert data['bookEntriesCreated']==data['providerRequests']==0
    assert data['counts']['linkedAllocations']==2
    assert all(g['accountId'] is None for g in data['accountGroups'])
    assert data['counts']['ready']==0
    assert client.post('/finance/import-review',headers=ben,json={'files':pack()}).status_code==403
    with app.state.sessions() as db:assert before=={t:db.scalar(select(func.count()).select_from(t)) for t in before}

def test_customer_identity_and_company_are_not_guessed():
    files=pack();rows=list(csv.DictReader(io.StringIO(files[2]['content'])));rows[0]['CustomerID']='another';files[2]=file('received.csv',rows)
    d=build(files,{},[])
    p=next(x for x in d['documents'] if x['kind']=='customer_payment')
    assert p['allocations'][0]['targetId'] is None and 'missing_target' in p['issues']
    assert next(x for x in d['documents'] if x['kind']=='bill')['company']=='unconfirmed'

def test_repeated_document_totals_are_not_summed_and_rows_are_not_deleted():
    rows=list(csv.DictReader(io.StringIO(pack()[0]['content'])));r=rows[0];r['Item Total']='50.00';r['Item Tax Amount']='6.00'
    docs,_,_=parse([file('invoice.csv',[r,r])]);d=docs[0]
    assert d['total']==11200 and d['subtotal']==10000 and len(d['lines'])==2
    assert 'duplicate_rows' in d['issues'] and 'components' not in d['issues']

def test_field_coverage_holds_unknown_financial_values_but_not_tax_ids():
    rows=list(csv.DictReader(io.StringIO(pack()[0]['content'])));rows[0]['Tax ID']='123456789';rows[0]['TotalRetentionAmountFCY']='5.00'
    docs,_,_=parse([file('invoice.csv',rows)])
    assert docs[0]['unhandledFields']==['TotalRetentionAmountFCY'] and 'unsupported_financial' in docs[0]['issues']

def test_aging_metadata_and_buckets_checked_not_filename():
    _,controls,_=parse([control()]);assert controls[0]['asOf']=='2025-12-31' and controls[0]['total']==1000
    with pytest.raises(ReviewError):parse([control('October 28, 2026')])
    broken=control();broken['content']=broken['content'].replace('10.00,0.00,0.00,0.00,10.00','9.00,0.00,0.00,0.00,10.00')
    with pytest.raises(ReviewError):parse([broken])

def test_payment_cash_and_withholding_stay_separate():
    files=pack();rows=list(csv.DictReader(io.StringIO(files[2]['content'])));rows[0]['Withholding Tax Amount']='1.00';files[2]=file('received.csv',rows)
    d=build(files,{},[]);p=next(x for x in d['documents'] if x['kind']=='customer_payment')
    assert p['total']==5600 and p['allocations'][0]['cash']==5600 and p['allocations'][0]['withheld']==100
    assert 'allocation' not in p['issues']

def test_same_source_selected_twice_and_malformed_inputs_are_rejected():
    with pytest.raises(ReviewError):parse(pack()+pack()[:1])
    with pytest.raises(ReviewError):parse([{'name':'bad.csv','content':'Invoice ID,Invoice ID\n1,1\n'}])
    with pytest.raises(ReviewError):parse([{'name':'bad.csv','content':'\x00'}])

def test_local_rehearsal_posts_actual_models_and_balanced_entries_separately(app,client,ana,tmp_path,monkeypatch):
    monkeypatch.setattr('app.import_rehearsal.DATA_DIR',tmp_path)
    choices=seed_choices(client,ana)
    result=client.post('/finance/import-review/rehearse',headers=ana,json={'files':pack(),'choices':choices,'confirm':True})
    assert result.status_code==200,result.text
    r=result.json();assert r['officialWrites']==0 and r['balanced'] and r['posted']=={'invoice':1,'bill':1,'customer_payment':1,'vendor_payment':1}
    assert r['receivablesCentavos']==5600 and r['payablesCentavos']==2800
    assert r['debitCentavos']==r['creditCentavos']==25200
    assert not r['completeBaseline'] and not r['taxReportsCertified']
    assert (tmp_path/'import-rehearsals'/f"{r['id']}.db").exists()
    with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(Invoice))==db.scalar(select(func.count()).select_from(Bill))==0

def test_official_environment_cannot_post_a_rehearsal(app,client,ana):
    app.state.settings.data_environment='official'
    r=client.post('/finance/import-review/rehearse',headers=ana,json={'files':pack(),'confirm':True})
    assert r.status_code==409


def mapped_review(files):
    accounts=[{'id':role,'code':role,'name':role,'type':kind,'active':True,'posting':True,'money':role=='money'}
              for role,kind in [('income','income'),('receivable','asset'),('output_tax','liability'),('cost','expense'),('payable','liability'),('input_tax','asset'),('money','asset')]]
    choices={'billCompanies':{'2MG':'2mg'}}
    first=build(files,choices,accounts)
    choices['accounts']={g['id']:g['role'] for g in first['accountGroups']}
    return build(files,choices,accounts)


@pytest.mark.parametrize('index,field,kind',[(2,'CustomerPayment ID','customer_payment'),(3,'VendorPayment ID','vendor_payment')])
def test_allocation_identity_cannot_be_reused_by_a_different_payment(index,field,kind):
    files=pack();rows=list(csv.DictReader(io.StringIO(files[index]['content'])))
    other=dict(rows[0]);other[field]='another-payment';other['Payment Number']='P-OTHER'
    files[index]=file('payments.csv',rows+[other])
    payments=[d for d in mapped_review(files)['documents'] if d['kind']==kind]
    assert len(payments)==2
    assert all('allocation_identity' in d['issues'] and not d['financialReady'] for d in payments)


def test_distinct_partial_payment_applications_remain_eligible():
    files=pack();rows=list(csv.DictReader(io.StringIO(files[2]['content'])))
    other=dict(rows[0]);other.update({'CustomerPayment ID':'p2','Payment Number':'P-2','InvoicePayment ID':'a2'})
    files[2]=file('received.csv',rows+[other])
    payments=[d for d in mapped_review(files)['documents'] if d['kind']=='customer_payment']
    assert len(payments)==2 and all(d['financialReady'] for d in payments)


@pytest.mark.parametrize('first,second,expected',[('0.00','1.00',None),('1.00','1.00',100)])
def test_withholding_from_every_bill_row_is_checked_without_summing_headers(first,second,expected):
    files=pack();row=list(csv.DictReader(io.StringIO(files[1]['content'])))[0]
    row.update({'Item Total':'25.00','Tax Amount':'3.00','TDS Amount':first})
    other=dict(row);other.update({'Item Name':'Second line','TDS Amount':second})
    files[1]=file('bills.csv',[row,other])
    bill=next(d for d in mapped_review(files)['documents'] if d['kind']=='bill')
    assert not bill['financialReady'] and bill['withheld']==expected
    assert [r['amount'] for r in bill['withholdingRows']]==[round(float(first)*100),round(float(second)*100)]
    assert ('withholding_basis' in bill['issues'])==(first!=second)


def test_conflicting_invoice_identity_blocks_posting_and_control_totals():
    from app.import_review import compare
    files=pack();row=list(csv.DictReader(io.StringIO(files[0]['content'])))[0]
    twin=dict(row);twin['Invoice ID']='i2'
    files[0]=file('invoices.csv',[row,twin])
    review=mapped_review(files);invoices=[d for d in review['documents'] if d['kind']=='invoice']
    assert all('document_identity' in d['issues'] and not d['financialReady'] for d in invoices)
    opening={'id':'open','kind':'ar','asOf':'2025-12-31','items':[],'issues':[],'total':0}
    closing={'id':'close','kind':'ar','asOf':'2026-03-31','items':[{'party':row['Customer Name'],'reference':'SOURCE-1','balance':22400}],'issues':[],'total':22400}
    result=compare(invoices,[opening,closing],{'controlsCompany':'2mg','controlsCurrency':'PHP','confirmControlReferences':True})[-1]
    assert result['identityConflict'] and result['status']=='Blocked: conflicting references'
    assert result['reconstructedTotal'] is None and result['difference'] is None


def test_even_balanced_rehearsal_inputs_are_not_certified_for_tax():
    review=mapped_review(pack())
    assert any(d['financialReady'] for d in review['documents'])
    assert not any(d['taxReady'] for d in review['documents'])


def test_control_does_not_treat_unsupported_supplier_withholding_as_zero():
    from app.import_review import compare
    files=pack();row=list(csv.DictReader(io.StringIO(files[1]['content'])))[0]
    row['TDS Amount']='1.00';files[1]=file('bills.csv',[row])
    docs=mapped_review(files)['documents']
    opening={'id':'open','kind':'ap','asOf':'2025-12-31','items':[],'issues':[],'total':0}
    closing={'id':'close','kind':'ap','asOf':'2026-03-31','items':[],'issues':[],'total':0}
    result=compare(docs,[opening,closing],{'controlsCompany':'2mg','controlsCurrency':'PHP','confirmControlReferences':True})[-1]
    assert result['status']=='Blocked: source amounts need review'
    assert result['reconstructedTotal'] is None and result['difference'] is None
