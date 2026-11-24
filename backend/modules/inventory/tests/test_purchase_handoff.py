"""Fictional 2MG receipts: explicit sending, no second stock movement, safe replies."""
import pytest
from sqlalchemy import select,func
from fastapi import HTTPException
from modules.inventory.main import create_app
from modules.inventory.models import User,Role,Movement
from modules.inventory.security import hash_password
from modules.inventory.business_events import OutboxEvent
from modules.inventory.purchase_handoff import ReceiptHandoff,accept_status,protect
from .conftest import settings_for,PEOPLE,PASSWORD,receive,level


@pytest.fixture
def app(tmp_path):
    a=create_app(settings_for(tmp_path,default_company='2mg',dev_companies=['2mg']))
    with a.state.sessions() as db:
        for who,role in PEOPLE.items():
            rid=db.scalar(select(Role.id).where(Role.name==role))
            db.add(User(email=who+'@example.com',full_name=who.title(),password_hash=hash_password(PASSWORD),role_id=rid))
        db.commit()
    yield a
    a.state.tenants.close()


def receipt(ana,world):
    po=ana.post('/inventory/purchase-orders',{'supplierId':world['supplier'],'warehouseId':world['mnl'],
        'lines':[{'productId':world['gloves'],'quantity':100,'unitCost':100}]})
    ana.post('/inventory/purchase-orders/'+po['id']+'/place')
    return receive(ana,None,[{'productId':world['gloves'],'quantity':60}],orderId=po['id'])


def test_counting_alone_does_not_send_and_two_clicks_send_once(app,ana,world):
    r=receipt(ana,world)
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ReceiptHandoff))==0
        movements=db.scalar(select(func.count()).select_from(Movement))
    first=ana.post('/inventory/receipts/'+r['id']+'/finance-handoff',{})
    again=ana.post('/inventory/receipts/'+r['id']+'/finance-handoff',{})
    assert first['state']==again['state']=='sending' and first['remaining']==60
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ReceiptHandoff))==1
        out=db.scalars(select(OutboxEvent).where(OutboxEvent.kind=='purchase.receipt_submitted')).all()
        assert len(out)==1 and out[0].slug=='2mg' and out[0].data['lines'][0]['quantity']==60
        assert db.scalar(select(func.count()).select_from(Movement))==movements
    assert level(ana,world['gloves'])['onHand']==60
    refused=ana.c.post('/data-cleanup/kinds/receipts/delete',headers=ana.h,json={'ids':[r['id']],'confirmPosted':True})
    assert refused.status_code==409 and 'Finance' in refused.text


def test_normal_receiver_does_not_gain_send_authority(app,ana,world,client,people):
    r=receipt(ana,world)
    assert client.post('/inventory/receipts/'+r['id']+'/finance-handoff',json={},headers=people['wes']).status_code==403
    # Any company sends its receipts to its own Finance; no separate switch (2026-11-24).
    assert client.post('/inventory/receipts/'+r['id']+'/finance-handoff',json={},headers=people['ana']).status_code==200


def test_finance_reply_is_versioned_and_cleanup_is_blocked(app,ana,world):
    r=receipt(ana,world);ana.post('/inventory/receipts/'+r['id']+'/finance-handoff',{})
    with app.state.sessions() as db:
        h=db.scalar(select(ReceiptHandoff));data={'schemaVersion':1,'handoffId':h.id,'receiptId':r['id'],'digest':h.digest,
            'version':2,'state':'partially_allocated','remaining':10,'reason':None,'bills':[{'id':'TEST-BILL','state':'draft'}]}
        accept_status(db,data,'2mg');db.commit()
        accept_status(db,data|{'version':1,'remaining':60},'2mg');db.commit()
        assert h.remaining==10
        with pytest.raises(HTTPException):protect(db,'receipt',r['id'])
        # A reply for another company is opened in that company's database (business_events), never here.
    saved=ana.get('/inventory/receipts/'+r['id'])
    assert saved['financeHandoff']['remaining']==10 and saved['financeHandoff']['state']=='partially_allocated'


def test_non_purchase_receipts_are_not_ordinary_supplier_bills(ana,world):
    r=receive(ana,world['mnl'],[{'productId':world['gloves'],'quantity':2}])
    ana.post('/inventory/receipts/'+r['id']+'/finance-handoff',{},expect=409)


def test_export_actual_receipt_contract(app,ana,world,tmp_path):
    import os,json
    from pathlib import Path
    r=receipt(ana,world);ana.post('/inventory/receipts/'+r['id']+'/finance-handoff',{})
    with app.state.sessions() as db:
        data=db.scalar(select(OutboxEvent).where(OutboxEvent.kind=='purchase.receipt_submitted')).data
    directory=Path(os.environ.get('PURCHASE_CONTRACT_DIR',str(tmp_path)));directory.mkdir(exist_ok=True,parents=True)
    (directory/'inventory-evidence.json').write_text(json.dumps(data),encoding='utf-8')
    assert data['lines'][0]['quantity']==60


def test_finance_reply_matches_the_inventory_contract(tmp_path):
    import os,json
    from pathlib import Path
    from modules.inventory.purchase_handoff import Reply,fingerprint
    directory=os.environ.get('PURCHASE_CONTRACT_DIR')
    if not directory:pytest.skip('Run the explicit cross-app contract rehearsal to supply both saved messages.')
    source=json.loads((Path(directory)/'inventory-evidence.json').read_text(encoding='utf-8'))
    answer=json.loads((Path(directory)/'finance-reply.json').read_text(encoding='utf-8'))
    validated=Reply.model_validate(answer)
    assert validated.handoffId==source['handoffId'] and validated.receiptId==source['receiptId']
    assert validated.digest==fingerprint(source) and validated.remaining==10
    assert len(validated.bills)==1 and validated.state=='partially_allocated'
