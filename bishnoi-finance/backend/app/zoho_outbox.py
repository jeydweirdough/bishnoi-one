"""Record delivery intent in the same transaction as approved Finance work."""
from datetime import timedelta
import hashlib,json,uuid
from sqlalchemy import select
from app.models import Bill,PaymentVoucher,ZohoDelivery,ZohoDeliveryEvent,ZohoLink,utcnow

LABELS={'waiting_to_send':'Waiting to send','waiting_for_setup':'Setup needed','waiting_for_bill':'Waiting for linked bills',
        'working':'Sending in background','sent':'Sent to Zoho','needs_attention':'Needs attention',
        'uncertain':'Check Zoho before retrying','cancelled':'Not being sent'}
REASONS={'write_access':'Reconnect Zoho with bill/payment permission.','mapping':'Confirm the supplier, account, tax and company mappings.',
         'linked_bill':'Wait for the linked bills to be confirmed in Zoho.','existing_reference':'This record already has a Zoho reference; link and verify it instead of creating it again.',
         'unknown_outcome':'Zoho may have received this request. Check for the existing record before trying again.',
         'changed_record':'The approved record changed or was voided. Review the existing Zoho record.',
         'provider_validation':'Zoho refused the details. Review the mappings and source document.',
         'rate_limit':'Zoho is busy; this job will retry later.','setup_disabled':'Live Zoho sending is not enabled.',
         'response_mismatch':'Zoho returned different amounts or relationships. Check the created record; do not send another.',
         'wrong_environment':'This record belongs to another Finance environment.'}
REASONS['withholding_review']='The Zoho withholding treatment needs Finance confirmation before this bill can be sent.'
REASONS['worker_error']='The updater could not finish safely. IT can inspect this job; do not create a second record.'


def event(db,job,kind,actor='Background updater',code=None):
    db.add(ZohoDeliveryEvent(delivery_id=job.id,kind=kind,actor=actor[:120],code=code))
    job.updated_at=utcnow()


def content(kind,record,db=None):
    if kind=='bill':
        from app.tax import rates
        from app.tax.packs.ph import VAT
        vat_bp=rates.lookup(db,'PH')(VAT,record.bill_date) if db is not None else None
        return {'id':record.id,'supplierId':record.supplier_id,'number':record.bill_number,
            'date':record.bill_date.isoformat(),'dueDate':record.due_date.isoformat(),
            'inclusive':record.amounts_include_vat,'lines':record.lines,'total':record.total_centavos,
            'withheld':record.withheld_centavos,'payable':record.payable_centavos,'entryId':record.entry_id,'vatBp':vat_bp}
    return {'id':record.id,'supplierId':record.supplier_id,'number':record.number,
        'date':record.paid_on.isoformat(),'amount':record.total_centavos,'paidFromId':record.paid_from_id,
        'method':record.method,'entryId':record.entry_id,'bankReference':record.bank_reference,
        'checkNumber':record.check_number,'checkDate':record.check_date.isoformat() if record.check_date else None,
        'lines':[{'billId':line.bill_id,'amount':line.amount_centavos,'billNumber':line.bill.bill_number,
                  'billDate':line.bill.bill_date.isoformat(),'billTotal':line.bill.total_centavos} for line in record.lines]}


def fingerprint(snapshot):return hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def enqueue(db,settings,kind,record,actor):
    if not settings.zoho_outbox_capture_enabled:return None
    eligible=record.status==('recorded' if kind=='bill' else 'released') and record.entry_id
    if not eligible:return None
    existing=db.scalar(select(ZohoDelivery).where(ZohoDelivery.environment==settings.data_environment,
        ZohoDelivery.kind==kind,ZohoDelivery.local_id==record.id))
    if existing:return existing
    snapshot=content(kind,record,db)
    from app.zoho_connection import saved_record
    try:org=((saved_record(settings).get('connection') or {}).get('organization') or {}).get('id','')
    except Exception:org=''  # A local posting must not wait on connection setup or Zoho.
    code='existing_reference' if record.zoho_ref else 'setup_disabled' if not settings.zoho_outbound_enabled else None
    identity=str(uuid.uuid4())
    job=ZohoDelivery(id=identity,environment=settings.data_environment,kind=kind,local_id=record.id,
        organization_id=org,reference='B1-'+('B-' if kind=='bill' else 'P-')+identity,
        snapshot=snapshot,fingerprint=fingerprint(snapshot),created_by=actor[:120],
        status='waiting_for_setup' if code else 'waiting_to_send',error_code=code)
    db.add(job);db.flush();event(db,job,'queued',actor,code)
    return job


def summary(db,kind,local_id):
    job=db.scalar(select(ZohoDelivery).where(ZohoDelivery.kind==kind,ZohoDelivery.local_id==local_id)
        .order_by(ZohoDelivery.created_at.desc()))
    if not job:return None
    return {'id':job.id,'status':job.status,'label':LABELS.get(job.status,'Needs attention'),
        'message':REASONS.get(job.error_code),'attempts':job.attempts,'remoteId':job.remote_id,
        'updatedAt':job.updated_at.isoformat()}


def invalidate(db,kind,local_id,actor):
    for job in db.scalars(select(ZohoDelivery).where(ZohoDelivery.kind==kind,ZohoDelivery.local_id==local_id)):
        job.status='needs_attention' if job.remote_id or job.attempts else 'cancelled'
        job.error_code='changed_record';job.owner=None;job.lease_until=None
        event(db,job,'local_record_voided',actor,'changed_record')


def claim(db,environment):
    now=utcnow()
    # A crashed in-flight POST is never blindly retried.
    expired=list(db.scalars(select(ZohoDelivery).where(ZohoDelivery.environment==environment,ZohoDelivery.status=='working',ZohoDelivery.lease_until<now).with_for_update(skip_locked=True)))
    for job in expired:
        job.status='uncertain';job.error_code='unknown_outcome';job.owner=None;event(db,job,'lease_expired',code='unknown_outcome')
    job=db.scalar(select(ZohoDelivery).where(ZohoDelivery.environment==environment,
        ZohoDelivery.status.in_(['waiting_to_send','waiting_for_setup','waiting_for_bill']),ZohoDelivery.next_attempt<=now)
        .order_by(ZohoDelivery.created_at).with_for_update(skip_locked=True).limit(1))
    if job:
        job.status='working';job.owner=uuid.uuid4().hex;job.lease_until=now+timedelta(seconds=120)
        event(db,job,'claimed')
    db.commit();return job


def mapping(db,org,kind,key):
    link=db.get(ZohoLink,(org,kind,str(key)))
    if not link or not link.confirmed:raise SetupNeeded('mapping')
    return link


class SetupNeeded(Exception):pass


def payload(db,job):
    snapshot=job.snapshot;org=job.organization_id
    vendor=mapping(db,org,'supplier',snapshot['supplierId']).remote_id
    if not vendor:raise SetupNeeded('mapping')
    if job.kind=='bill':
        company=mapping(db,org,'company','2mg').details
        if not company.get('fieldId') or not company.get('value'):raise SetupNeeded('mapping')
        lines=[]
        for line in snapshot['lines']:
            account=mapping(db,org,'account',line['accountId']).remote_id
            tax=mapping(db,org,'vat',line['vat'])
            if not account:raise SetupNeeded('mapping')
            item={'account_id':account,'description':line.get('description',''),'quantity':1,'rate':line['amountCentavos']/100}
            if tax.remote_id:item['tax_id']=tax.remote_id
            elif not tax.details.get('confirmedNoTax'):raise SetupNeeded('mapping')
            if line.get('withholding'):
                held=mapping(db,org,'withholding',line['withholding']).remote_id
                if not held:raise SetupNeeded('mapping')
                item['tds_tax_id']=held
            lines.append(item)
        return {'vendor_id':vendor,'bill_number':snapshot['number'],'date':snapshot['date'],'due_date':snapshot['dueDate'],
            'is_inclusive_tax':snapshot['inclusive'],'reference_number':job.reference,'line_items':lines,
            'custom_fields':[{'custom_field_id':company['fieldId'],'value':company['value']}]}
    paid=mapping(db,org,'money_account',snapshot['paidFromId']).remote_id
    if not paid:raise SetupNeeded('mapping')
    allocations=[]
    for line in snapshot['lines']:
        source_bill=db.get(Bill,line['billId'])
        if not source_bill or source_bill.withheld_centavos:raise SetupNeeded('withholding_review')
        try:bill=mapping(db,org,'bill',line['billId']).remote_id
        except SetupNeeded:raise SetupNeeded('linked_bill') from None
        if not bill:raise SetupNeeded('linked_bill')
        allocations.append({'bill_id':bill,'amount_applied':line['amount']/100})
    return {'vendor_id':vendor,'date':snapshot['date'],'amount':snapshot['amount']/100,
        'payment_mode':{'bank':'Bank Transfer','check':'Check','cash':'Cash'}.get(snapshot['method'],'Cash'),
        'paid_through_account_id':paid,'reference_number':job.reference,'bills':allocations,
        'description':('Finance '+snapshot['number']+'; '+(snapshot.get('bankReference') or snapshot.get('checkNumber') or ''))[:500]}
