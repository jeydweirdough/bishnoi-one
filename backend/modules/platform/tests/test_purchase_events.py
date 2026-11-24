"""Both handoff directions have explicit source/target routes; existing queue is reused."""
from datetime import datetime,timezone
import uuid
from sqlalchemy import select,func
from modules.platform import events
from modules.platform.models import BusinessEvent,EventDelivery
from .conftest import app_id,make_company


def test_purchase_routes_are_source_bound_durable_and_duplicate_safe(app,client,ana,monkeypatch):
    company=make_company(client,ana,apps=('inventory','finance'))
    keys={key:client.post(f"/platform/applications/{app_id(client,ana,key)}/connect-key",headers=ana).json()['key'] for key in ('inventory','finance')}
    monkeypatch.setattr(events,'kick',lambda *_:None)
    def send(kind,source):
        id=str(uuid.uuid4());body={'company':company['slug'],'events':[{'id':id,'kind':kind,'data':{'schemaVersion':1},'occurredAt':datetime.now(timezone.utc).isoformat()}]}
        return id,body,client.post('/connect/events',headers={'X-Bishnoi-App-Key':keys[source]},json=body)
    first,body,r=send('purchase.receipt_submitted','inventory')
    assert r.status_code==200 and r.json()['taken']==[first]
    assert client.post('/connect/events',headers={'X-Bishnoi-App-Key':keys['inventory']},json=body).json()['taken']==[first]
    reply,_,r=send('purchase.receipt_finance_updated','finance');assert r.json()['taken']==[reply]
    wrong,_,r=send('purchase.receipt_submitted','finance');assert r.json()['refused']==[wrong]
    with app.state.sessions() as db:
        assert db.get(EventDelivery,(first,'finance')).status=='pending'
        assert db.get(EventDelivery,(reply,'inventory')).status=='pending'
        assert db.get(BusinessEvent,wrong) is None
        assert db.scalar(select(func.count()).select_from(EventDelivery).where(EventDelivery.event_id==first))==1
