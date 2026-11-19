"""Fictional receipt-to-bill evidence, atomic allocation and independent approval."""
import uuid
import pytest
from sqlalchemy import select,func
from fastapi import HTTPException
from modules.finance.models import Bill,JournalEntry,CompanyScopeReview
from modules.finance.purchase_intake import PurchaseIntake,PurchaseAllocation,receive,protect_bill
from .test_tax_api import app,client,ana
from .test_payables import supplier,account


def evidence(**changes):
    return {'schemaVersion':1,'handoffId':str(uuid.uuid4()),'receiptId':str(uuid.uuid4()),'receiptNumber':'TEST-RC-1',
        'orderId':'TEST-PO-ID','orderNumber':'TEST-PO-1','supplierId':'TEST-INV-VENDOR','supplierName':'TEST vendor',
        'supplierTin':None,'currencyEvidence':'PHP','deliveryRef':'TEST delivery only','receivedAt':'2026-11-11T00:00:00+00:00',
        'receivedBy':'TEST receiver','qualityReady':True,
        'lines':[{'id':'TEST-line-1','orderLineId':'TEST-order-line','productId':'TEST-product','unitCode':'box','product':'TEST medicine','unit':'box','quantity':60,'unitCost':100}],**changes}


def intake(app,client,ana,data=None):
    data=data or evidence()
    with app.state.sessions() as db:receive(db,data,'2mg');db.commit()
    rows=client.get('/finance/purchase-intakes',headers=ana).json()['items']
    return next(x for x in rows if x['snapshot']['receiptId']==data['receiptId'])


def linked(app,client,ana,item):
    s=supplier(client,ana,name='TEST verified purchase vendor')
    r=client.post('/finance/purchase-intakes/'+item['id']+'/supplier',headers=ana,json={'version':item['version'],'supplierId':s['id'],'evidence':'TEST reviewed source identity'})
    assert r.status_code==200,r.text
    return r.json(),s


def request(client,ana,item,s,quantity=60):
    return {'requestId':str(uuid.uuid4()),'sourceReviewed':True,
        'allocations':[{'intakeId':item['id'],'sourceLineId':'TEST-line-1','quantity':quantity,'version':item['version']}],
        'bill':{'supplierId':s['id'],'billNumber':'TEST-invoice','billDate':'2026-11-11','taxReviewed':True,
            'lines':[{'accountId':account(client,ana,'6500'),'amountCentavos':quantity*100,'vat':'none','withholding':None,'noWithholdingReason':'not_covered'}]}}


def test_receive_is_durable_held_once_without_bill_or_journal(app,client,ana):
    data=evidence();a=intake(app,client,ana,data);b=intake(app,client,ana,data)
    assert a['id']==b['id'] and a['state']=='held' and a['remaining']==60
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(PurchaseIntake))==1
        assert db.scalar(select(func.count()).select_from(Bill))==0
        assert db.scalar(select(func.count()).select_from(JournalEntry))==0


def test_partial_invoice_retry_stale_and_overallocation(app,client,ana):
    item,s=linked(app,client,ana,intake(app,client,ana))
    body=request(client,ana,item,s,50)
    first=client.post('/finance/purchase-intakes/prepare',headers=ana,json=body)
    assert first.status_code==201,first.text
    assert len(first.json()['purchaseEvidence'])==1
    again=client.post('/finance/purchase-intakes/prepare',headers=ana,json=body)
    assert again.status_code==201 and again.json()['id']==first.json()['id']
    saved=client.get('/finance/purchase-intakes/'+item['id'],headers=ana).json()
    assert saved['remaining']==10 and saved['state']=='partially_allocated'
    stale=request(client,ana,item,s,10)
    assert client.post('/finance/purchase-intakes/prepare',headers=ana,json=stale).status_code==409
    too_much=request(client,ana,saved,s,11)
    assert client.post('/finance/purchase-intakes/prepare',headers=ana,json=too_much).status_code==409
    with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(Bill))==1


def test_draft_cancellation_releases_quantities_but_keeps_evidence(app,client,ana):
    item,s=linked(app,client,ana,intake(app,client,ana));body=request(client,ana,item,s)
    b=client.post('/finance/purchase-intakes/prepare',headers=ana,json=body).json()
    assert client.delete('/finance/bills/'+b['id'],headers=ana).status_code==409
    with app.state.sessions() as db:
        with pytest.raises(HTTPException):protect_bill(db,b['id'])
    r=client.post('/finance/purchase-intakes/bills/'+b['id']+'/cancel-draft',headers=ana)
    assert r.status_code==200,r.text
    assert client.get('/finance/purchase-intakes/'+item['id'],headers=ana).json()['remaining']==60
    with app.state.sessions() as db:
        assert db.get(Bill,b['id']).status=='void'
        assert db.scalar(select(func.count()).select_from(PurchaseAllocation))==1


def test_unknown_supplier_quality_and_source_correction_holds(app,client,ana):
    data=evidence(qualityReady=False);item,s=linked(app,client,ana,intake(app,client,ana,data))
    body=request(client,ana,item,s)
    assert client.post('/finance/purchase-intakes/prepare',headers=ana,json=body).status_code==409
    with app.state.sessions() as db:receive(db,data|{'orderNumber':'TEST changed'},'2mg');db.commit()
    held=client.get('/finance/purchase-intakes/'+item['id'],headers=ana).json()
    assert held['state']=='needs_correction' and held['snapshot']['orderNumber']=='TEST-PO-1'


def test_reclassified_supplier_stops_prepared_bill_submission(app,client,ana):
    item,s=linked(app,client,ana,intake(app,client,ana));body=request(client,ana,item,s)
    b=client.post('/finance/purchase-intakes/prepare',headers=ana,json=body).json()
    with app.state.sessions() as db:db.get(CompanyScopeReview,('supplier',s['id'])).scope='review';db.commit()
    assert client.post('/finance/bills/'+b['id']+'/submit',headers=ana).status_code==409


def test_missing_invoice_and_forged_line_or_company_cannot_prepare(app,client,ana):
    item,s=linked(app,client,ana,intake(app,client,ana));body=request(client,ana,item,s)
    body['bill']['billNumber']=''
    assert client.post('/finance/purchase-intakes/prepare',headers=ana,json=body).status_code==422
    body=request(client,ana,item,s);body['allocations'][0]['sourceLineId']='other-receipt-line'
    assert client.post('/finance/purchase-intakes/prepare',headers=ana,json=body).status_code==422
    with app.state.sessions() as db:
        with pytest.raises(HTTPException):receive(db,evidence(),'gpi')


def test_source_bill_keeps_independent_approval_and_signed_evidence(app,client,ana):
    from modules.finance.routers.payables import bill_content
    item,s=linked(app,client,ana,intake(app,client,ana));body=request(client,ana,item,s)
    b=client.post('/finance/purchase-intakes/prepare',headers=ana,json=body).json()
    with app.state.sessions() as db:assert bill_content(db.get(Bill,b['id']))['purchaseEvidence'][0]['quantity']==60
    submitted=client.post('/finance/bills/'+b['id']+'/submit',headers=ana)
    assert submitted.status_code==200,submitted.text
    assert client.post('/finance/bills/'+b['id']+'/approve',headers=ana).status_code==403
    assert client.post('/finance/purchase-intakes/bills/'+b['id']+'/cancel-draft',headers=ana).status_code==409


def test_concurrent_last_quantity_and_same_invoice_are_not_billed_twice(app,client,ana):
    from concurrent.futures import ThreadPoolExecutor
    item,s=linked(app,client,ana,intake(app,client,ana));first=request(client,ana,item,s,50)
    assert client.post('/finance/purchase-intakes/prepare',headers=ana,json=first).status_code==201
    latest=client.get('/finance/purchase-intakes/'+item['id'],headers=ana).json()
    a=request(client,ana,latest,s,10);a['bill']['billNumber']='TEST-final-A'
    b=request(client,ana,latest,s,10);b['bill']['billNumber']='TEST-final-B'
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(lambda body:client.post('/finance/purchase-intakes/prepare',headers=ana,json=body).status_code,(a,b)))
    assert sorted(outcomes)==[201,409]
    with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(Bill))==2


def test_lost_browser_request_key_still_cannot_duplicate_the_supplier_invoice(app,client,ana):
    item,s=linked(app,client,ana,intake(app,client,ana));a=request(client,ana,item,s,10)
    assert client.post('/finance/purchase-intakes/prepare',headers=ana,json=a).status_code==201
    latest=client.get('/finance/purchase-intakes/'+item['id'],headers=ana).json()
    duplicate=request(client,ana,latest,s,10)
    assert client.post('/finance/purchase-intakes/prepare',headers=ana,json=duplicate).status_code==409


def test_signed_inventory_event_persists_held_evidence_and_rejects_wrong_source(app,client,ana):
    from .test_platform_roles import note
    from .test_platform_sign_in import PUBLIC
    app.state.settings.platform_public_key=PUBLIC
    data=evidence();event={'id':str(uuid.uuid4()),'kind':'purchase.receipt_submitted','source':'inventory','data':data}
    for _ in range(2):assert client.post('/platform/events',json={'pass':note('event',slug='2mg',event=event)}).status_code==204
    assert len(client.get('/finance/purchase-intakes',headers=ana).json()['items'])==1
    bad=event|{'id':str(uuid.uuid4()),'source':'crm'}
    assert client.post('/platform/events',json={'pass':note('event',slug='2mg',event=bad)}).status_code==409


def test_prepare_from_the_inventory_emitted_contract(app,client,ana,tmp_path):
    import os,json
    from pathlib import Path
    from modules.finance.business_events import OutboxEvent
    folder=os.environ.get('PURCHASE_CONTRACT_DIR')
    data=json.loads((Path(folder)/'inventory-evidence.json').read_text(encoding='utf-8')) if folder else evidence()
    item,s=linked(app,client,ana,intake(app,client,ana,data));body=request(client,ana,item,s,50)
    body['allocations'][0]['sourceLineId']=data['lines'][0]['id']
    r=client.post('/finance/purchase-intakes/prepare',headers=ana,json=body)
    assert r.status_code==201,r.text
    with app.state.sessions() as db:
        answer=db.scalar(select(OutboxEvent).where(OutboxEvent.kind=='purchase.receipt_finance_updated').order_by(OutboxEvent.occurred_at.desc())).data
    directory=Path(folder) if folder else tmp_path
    (directory/'finance-reply.json').write_text(json.dumps(answer),encoding='utf-8')
    assert answer['remaining']==10 and answer['receiptId']==data['receiptId']


def test_manual_review_hold_can_resume_but_changed_source_cannot(app,client,ana):
    item=intake(app,client,ana)
    r=client.post('/finance/purchase-intakes/'+item['id']+'/return',headers=ana,json={'version':item['version'],'reason':'TEST confirm receiving evidence'})
    assert r.status_code==200
    resumed=client.post('/finance/purchase-intakes/'+item['id']+'/resume',headers=ana,json={'version':r.json()['version'],'reason':'TEST unchanged evidence verified'})
    assert resumed.status_code==200 and resumed.json()['state']=='held'
    data=evidence();conflict=intake(app,client,ana,data)
    with app.state.sessions() as db:receive(db,data|{'orderNumber':'TEST changed'},'2mg');db.commit()
    conflict=client.get('/finance/purchase-intakes/'+conflict['id'],headers=ana).json()
    refused=client.post('/finance/purchase-intakes/'+conflict['id']+'/resume',headers=ana,json={'version':conflict['version'],'reason':'TEST cannot bypass changed source'})
    assert refused.status_code==409


def test_received_queue_pages_and_supplier_edit_does_not_grant_bill_access(app,client,ana):
    from .test_dashboard import person
    for _ in range(3):intake(app,client,ana)
    page=client.get('/finance/purchase-intakes?limit=1&offset=1',headers=ana)
    assert page.status_code==200 and page.json()['total']==3 and len(page.json()['items'])==1
    assert client.get('/finance/purchase-intakes?limit=101',headers=ana).status_code==422
    item=page.json()['items'][0];s=supplier(client,ana,name='TEST supplier edit access')
    editor=person(client,ana,'TEST supplier-only editor',['suppliers.view','suppliers.edit'])
    refused=client.post('/finance/purchase-intakes/'+item['id']+'/supplier',headers=editor,json={'version':item['version'],'supplierId':s['id'],'evidence':'TEST reviewed'})
    assert refused.status_code==403


def test_one_invoice_can_allocate_two_receipts_without_merging_their_quantities(app,client,ana):
    a,s=linked(app,client,ana,intake(app,client,ana));b=intake(app,client,ana)
    body=request(client,ana,a,s,5);body['bill']['billNumber']='TEST combined invoice'
    body['allocations'].append({'intakeId':b['id'],'sourceLineId':'TEST-line-1','quantity':10,'version':b['version']})
    body['bill']['lines'].append(body['bill']['lines'][0]|{'amountCentavos':1000})
    result=client.post('/finance/purchase-intakes/prepare',headers=ana,json=body)
    assert result.status_code==201,result.text
    assert len(result.json()['purchaseEvidence'])==2
    assert client.get('/finance/purchase-intakes/'+a['id'],headers=ana).json()['remaining']==55
    assert client.get('/finance/purchase-intakes/'+b['id'],headers=ana).json()['remaining']==50


def test_foreign_receipt_is_held_under_unified_php_only_bill_contract(app,client,ana):
    item=intake(app,client,ana,evidence(currencyEvidence='USD'))
    item,s=linked(app,client,ana,item)
    assert any('Only PHP bills' in h for h in item['holds'])
    response=client.post('/finance/purchase-intakes/prepare',headers=ana,json=request(client,ana,item,s))
    assert response.status_code==409
    with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(Bill))==0
