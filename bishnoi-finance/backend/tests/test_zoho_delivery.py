"""Synthetic queues only. No real provider requests or official database writes."""
from datetime import timedelta
from types import SimpleNamespace
import pytest
from sqlalchemy import select,func
from app.models import ZohoDelivery,ZohoLink,utcnow
from app.zoho_outbox import enqueue,claim,SetupNeeded,invalidate
from app.zoho_delivery import process,UnknownOutcome,RateLimited
from .test_vouchers import app,client,ana,ben,team,ready_bill,prepare,step


def enable(app):
    app.state.settings.zoho_outbox_capture_enabled=True
    app.state.settings.data_environment='official'


def jobs(app):
    with app.state.sessions() as db:return list(db.scalars(select(ZohoDelivery)))


def test_only_final_approval_and_release_queue_without_provider(app,client,ana,team,monkeypatch):
    enable(app)
    monkeypatch.setattr('httpx.HTTPTransport.handle_request',lambda *a,**k:pytest.fail('Foreground must never contact Zoho'))
    s,b=ready_bill(client,team)
    assert len(jobs(app))==1
    assert jobs(app)[0].status=='waiting_for_setup'
    v=prepare(client,team['cristal'],s,[{'billId':b['id'],'amountCentavos':10000}])
    assert len(jobs(app))==1
    step(client,team['cristal'],v,'submit')
    step(client,team['cristal'],v,'release',{'paidOn':'2026-10-04','bankReference':'synthetic-ref'})
    assert len(jobs(app))==2
    from app.models import PaymentVoucher
    from app.zoho_outbox import content,fingerprint
    payment=next(j for j in jobs(app) if j.kind=='vendor_payment')
    assert payment.snapshot['bankReference']=='synthetic-ref'
    with app.state.sessions() as db:
        assert payment.fingerprint==fingerprint(content('vendor_payment',db.get(PaymentVoucher,v['id']),db))
    assert client.get(f"/finance/bills/{b['id']}",headers=team['aubrey']).json()['zohoSync']['label']=='Setup needed'
    assert client.get('/finance/integrations/zoho/deliveries',headers=team['aubrey']).status_code==403
    assert client.get('/finance/integrations/zoho/deliveries',headers=ana).json()['total']==2


def test_posting_and_enqueue_rollback_together(app,client,team,monkeypatch):
    from .test_payables import supplier,bill
    enable(app);s=supplier(client,team['aubrey']);b=bill(client,team['aubrey'],s['id'])
    client.post(f"/finance/bills/{b['id']}/submit",headers=team['aubrey'])
    client.post(f"/finance/bills/{b['id']}/approve",headers=team['malou'])
    def fail(*a,**k):raise RuntimeError('synthetic queue failure')
    monkeypatch.setattr('app.zoho_outbox.enqueue',fail)
    with pytest.raises(RuntimeError):client.post(f"/finance/bills/{b['id']}/check",headers=team['rommel'])
    assert not jobs(app)
    assert client.get(f"/finance/bills/{b['id']}",headers=team['aubrey']).json()['state']=='to_check'


class Sender:
    organization='synthetic-org'
    created=0
    remote=None
    error=None
    def ready(self,kind):pass
    def find(self,kind,ref):return self.remote
    def validate(self,*args):pass
    def create(self,kind,body):
        self.created+=1
        if self.error:raise self.error()
        return {'bill_id':'remote-1','vendor_id':body['vendor_id'],'date':body['date'],
                'reference_number':body['reference_number'],'bill_number':body['bill_number'],'total':11200}


def setup_job(app,client,team):
    enable(app);s,b=ready_bill(client,team)
    with app.state.sessions() as db:
        j=db.scalar(select(ZohoDelivery));j.organization_id='synthetic-org';j.status='waiting_to_send';j.error_code=None
        db.commit();j=claim(db,'official');identifier=j.id
        body={'vendor_id':'vendor-1','date':j.snapshot['date'],'reference_number':j.reference,'bill_number':j.snapshot['number']}
    return identifier,body


def test_unknown_outcome_is_held_and_reconcile_never_posts(app,client,team,monkeypatch):
    identifier,body=setup_job(app,client,team)
    monkeypatch.setattr('app.zoho_delivery.payload',lambda *a:body)
    sender=Sender();sender.error=UnknownOutcome
    process(app.state.sessions,app.state.settings,identifier,sender)
    assert jobs(app)[0].status=='uncertain' and sender.created==1
    with app.state.sessions() as db:assert claim(db,'official') is None
    process(app.state.sessions,app.state.settings,identifier,sender,reconcile_only=True)
    assert sender.created==1
    sender.remote={'bill_id':'remote-1','vendor_id':'vendor-1','date':body['date'],
        'reference_number':body['reference_number'],'bill_number':body['bill_number'],'total':11200}
    process(app.state.sessions,app.state.settings,identifier,sender,reconcile_only=True)
    assert jobs(app)[0].status=='sent' and sender.created==1


def test_duplicate_claim_and_crash_hold(app,client,team):
    identifier,_=setup_job(app,client,team)
    with app.state.sessions() as db:
        assert claim(db,'official') is None
        j=db.get(ZohoDelivery,identifier);j.lease_until=utcnow()-timedelta(seconds=1);db.commit()
        assert claim(db,'official') is None
        assert db.get(ZohoDelivery,identifier).status=='uncertain'


def test_void_cancels_unsent_but_holds_sent(app,client,team):
    identifier,_=setup_job(app,client,team)
    with app.state.sessions() as db:
        j=db.get(ZohoDelivery,identifier);invalidate(db,'bill',j.local_id,'Reviewer');db.commit()
        assert j.status=='cancelled'
        j.remote_id='remote-1';invalidate(db,'bill',j.local_id,'Reviewer');db.commit()
        assert j.status=='needs_attention'


def test_existing_manual_reference_never_posts_a_second_bill(app,client,team,monkeypatch):
    from app.models import Bill
    identifier,body=setup_job(app,client,team)
    monkeypatch.setattr('app.zoho_delivery.payload',lambda *a:body)
    with app.state.sessions() as db:
        job=db.get(ZohoDelivery,identifier);db.get(Bill,job.local_id).zoho_ref='already-entered';db.commit()
    sender=Sender();process(app.state.sessions,app.state.settings,identifier,sender)
    assert sender.created==0 and jobs(app)[0].error_code=='existing_reference'


def test_mismatched_created_amount_is_held_with_remote_identity(app,client,team,monkeypatch):
    identifier,body=setup_job(app,client,team)
    monkeypatch.setattr('app.zoho_delivery.payload',lambda *a:body)
    sender=Sender();sender.remote={'bill_id':'remote-1','vendor_id':'vendor-1','date':body['date'],
        'reference_number':body['reference_number'],'bill_number':body['bill_number'],'total':1}
    process(app.state.sessions,app.state.settings,identifier,sender)
    j=jobs(app)[0]
    assert j.status=='needs_attention' and j.remote_id=='remote-1' and sender.created==0


def test_local_testing_cannot_use_live_sender(app):
    from app.zoho_delivery import ZohoSender
    with pytest.raises(SetupNeeded):ZohoSender(app.state.settings)


def test_company_echo_must_match_before_confirming_delivery():
    from app.zoho_delivery import matches
    job=SimpleNamespace(kind='bill',reference='ref',snapshot={'total':10000})
    body={'vendor_id':'vendor','date':'2026-10-01','bill_number':'S-1',
          'custom_fields':[{'custom_field_id':'company','value':'2MG'}]}
    remote={'reference_number':'ref','vendor_id':'vendor','date':'2026-10-01','bill_number':'S-1','total':100}
    assert not matches(job,body,remote)
    remote['custom_fields']=[{'custom_field_id':'company','value':'2MG'}]
    assert matches(job,body,remote)
