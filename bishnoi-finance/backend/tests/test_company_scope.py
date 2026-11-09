from app.models import CompanyScopeReview, CompanyReviewBatch, CompanyReviewRow
from .test_tax_api import app, client, ana  # noqa: F401
from .test_payables import supplier, bill


def scope(app, kind, id, value):
    with app.state.sessions() as db:
        db.add(CompanyScopeReview(subject_kind=kind, subject_id=id, scope=value, evidence={'source':'fictional'}, reviewed_by='TEST'))
        db.commit()


def test_normal_supplier_list_and_new_choices_are_only_reviewed_2mg(app, client, ana):
    a=supplier(client, ana, name='TEST 2MG vendor')
    b=supplier(client, ana, name='TEST other vendor',tin=None)
    scope(app,'supplier',a['id'],'2mg')
    scope(app,'supplier',b['id'],'review')
    normal=client.get('/finance/suppliers/review',headers=ana).json()
    assert [r['id'] for r in normal['items']]==[a['id']]
    all_rows=client.get('/finance/suppliers/review?company_use=all',headers=ana).json()
    assert all_rows['total']==2
    choices=client.get('/finance/bills/choices',headers=ana).json()
    assert [r['id'] for r in choices['suppliers']]==[a['id']]


def test_existing_bill_supplier_remains_available_but_not_for_new_bill(app,client,ana):
    a=supplier(client,ana,name='TEST legacy vendor')
    existing=bill(client,ana,a['id'])
    scope(app,'supplier',a['id'],'legacy')
    choices=client.get('/finance/bills/choices',params={'billId':existing['id']},headers=ana).json()
    assert any(r['id']==a['id'] for r in choices['suppliers'])
    line=existing['lines'][0]
    payload={'taxReviewed':True,'supplierId':a['id'],'billNumber':'TEST-NEW','billDate':'2026-10-01',
             'lines':[{k:line[k] for k in ('accountId','amountCentavos','vat','withholding')}]}
    response=client.post('/finance/bills',json=payload,headers=ana)
    assert response.status_code==422 and 'not verified for 2MG' in response.text
    payload['billNumber']=existing['billNumber']
    assert client.put('/finance/bills/'+existing['id'],json=payload,headers=ana).status_code==200
    assert client.get('/finance/bills/'+existing['id'],headers=ana).json()['supplier']['id']==a['id']


def test_chart_scope_keeps_all_history_reachable(app,client,ana):
    all_rows=client.get('/finance/ledger/accounts',headers=ana).json()['items']
    scope(app,'account',all_rows[0]['id'],'2mg')
    scope(app,'account',all_rows[1]['id'],'legacy')
    visible=client.get('/finance/ledger/accounts?company_use=2mg',headers=ana).json()['items']
    assert [r['id'] for r in visible]==[all_rows[0]['id']]
    assert len(client.get('/finance/ledger/accounts',headers=ana).json()['items'])==len(all_rows)


def test_manual_supplier_entry_stays_available_in_2mg_context(app,client,ana):
    first=supplier(client,ana,name='TEST existing 2MG')
    scope(app,'supplier',first['id'],'2mg')
    added=supplier(client,ana,name='TEST newly entered',tin=None)
    assert added['id'] in {s['id'] for s in client.get('/finance/suppliers/review',headers=ana).json()['items']}
