import csv
import io
from datetime import date
from app import bir_reports as bir
from .test_tax_api import app, client, ana, ben
from .test_invoices import ready, issued
from .test_payables import supplier, bill


def read(r):
    assert r.status_code == 200, r.text
    assert r.headers['content-type'].startswith('text/csv')
    return list(csv.DictReader(io.StringIO(r.content.decode('utf-8-sig'))))


def test_vat_monthly_export_uses_plain_labels_and_peso_amounts(client, ana):
    rows = read(client.get('/finance/exports/bir-review/vat.csv?year=2026&quarter=1', headers=ana))
    monthly = [r for r in rows if r['Section'] == 'Monthly']
    assert len(monthly) == 21
    assert all('Centavos' not in r['Item'] for r in monthly)
    assert {r['Item'].split(': ', 1)[1] for r in monthly} == {
        'VATable sales', 'Output VAT', 'Zero-rated sales', 'VAT-exempt sales',
        'Non-VAT sales', 'Purchases before VAT', 'Input VAT',
    }
    assert all(r['Amount PHP'] == '0.00' for r in monthly)


def test_calculated_monthly_withholding_is_not_remittance(monkeypatch):
    monkeypatch.setattr(bir, 'withheld_bills', lambda *a, **k: [])
    monkeypatch.setattr(bir, 'by_atc', lambda *a: [{'taxCentavos': 10000}])
    monkeypatch.setattr(bir, 'form_0619e', lambda *a: {'totalCentavos': 2000})
    d = bir.form_1601eq(None, bir.quarter(2026,1))
    assert d['totalCentavos'] == 10000
    assert d['dueCentavos'] is None
    assert all(r['amountCentavos'] is None for r in d['remitted'])
    assert [r['calculatedWithholdingCentavos'] for r in d['remitted']] == [2000,2000]


def test_empty_permissions_and_dates(client, ana):
    for kind in ['bills','bill-lines','invoices','customer-payments','supplier-payments','payment-allocations','petty-cash','petty-cash-lines','imported-expenses','imported-expense-lines']:
        url=f'/finance/exports/review/{kind}.csv'
        assert client.get(url).status_code == 401
        assert read(client.get(url, headers=ana)) == []
        assert client.get(url+'?start=2026-03-01&end=2026-01-01',headers=ana).status_code == 422
    for kind in ['vat','vat-sources','0619e','1601eq','2307']:
        url=f'/finance/exports/bir-review/{kind}.csv?year=2026&quarter=1'
        assert client.get(url).status_code == 401
        read(client.get(url,headers=ana))


def test_document_and_line_totals_and_text_safety(client, ana, ben):
    s=supplier(client,ben,name='=DANGER')
    b=bill(client,ben,s['id'])
    docs=read(client.get('/finance/exports/review/bills.csv',headers=ana))
    lines=read(client.get('/finance/exports/review/bill-lines.csv',headers=ana))
    assert len(docs)==len(lines)==1
    assert docs[0]['Supplier']=="'=DANGER"
    assert docs[0]['Gross PHP']==f"{b['totalCentavos']/100:.2f}"
    assert 'Gross PHP' not in lines[0]
    assert read(client.get('/finance/exports/review/bills.csv?start=2026-11-01',headers=ana))==[]


def test_invoice_and_receipts_keep_cash_and_withholding_separate(client,ana,ben):
    ready(client,ana)
    inv=issued(client,ben)
    r=client.post('/finance/invoices/'+inv['id']+'/payments',headers=ben,json={'paidOn':date.today().isoformat(),'amountCentavos':220000,'method':'bank','cwtCentavos':4000,'cwtAtc':'WC158','cwtCertificate':'TEST'})
    assert r.status_code==201,r.text
    row=read(client.get('/finance/exports/review/customer-payments.csv',headers=ana))[0]
    assert row['Cash PHP']=='2200.00' and row['Customer withholding PHP']=='40.00'
    assert row['Payment status']=='recorded'
    assert read(client.get('/finance/exports/review/invoices.csv?status=void',headers=ana))==[]


def test_export_is_not_limited_to_screen_page_and_permissions_are_kept(client,ana,app):
    from app.models import Invoice
    from .test_dashboard import person,VIEW
    with app.state.sessions() as db:
        db.add_all([Invoice(customer_name='CSV pagination test',invoice_date=date(2026,1,1),lines=[],created_by='Test',treatment='regular') for _ in range(205)])
        db.commit()
    rows=read(client.get('/finance/exports/review/invoices.csv?q=CSV%20pagination',headers=ana))
    assert len(rows)==205
    outsider=person(client,ana,'No record access',['dashboard.view'])
    for kind in ['bills','supplier-payments','petty-cash','invoices']:
        assert client.get('/finance/exports/review/'+kind+'.csv',headers=outsider).status_code==403
    assert client.get('/finance/exports/bir-review/vat.csv',headers=outsider).status_code==403


def test_posted_bill_detail_keeps_line_values_and_foreign_currency(client,ana,ben):
    from .test_payables import account, cleared
    from decimal import Decimal
    s=supplier(client,ben)
    line={'accountId':account(client,ben,'6500'),'amountCentavos':11200,'vat':'vat','withholding':None,'purchaseType':'other_goods'}
    b=bill(client,ben,s['id'],lines=[line,line],currency='USD',rate=56)
    cleared(client,ana,ben,b)
    rows=read(client.get('/finance/exports/review/bill-lines.csv',headers=ana))
    assert len(rows)==2 and all(r['Currency']=='USD' for r in rows)
    assert sum(Decimal(r['Net (bill currency)']) for r in rows)==200
    assert sum(Decimal(r['VAT (bill currency)']) for r in rows)==24
    docs=read(client.get('/finance/exports/review/bills.csv',headers=ana))
    assert docs[0]['Gross PHP']=='12544.00'
