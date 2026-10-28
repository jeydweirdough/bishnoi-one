"""Bounded background-only Zoho sending. Unknown POST outcomes never auto-resend."""
from decimal import Decimal,ROUND_HALF_UP,InvalidOperation
from datetime import timedelta
import re,time
import httpx
from sqlalchemy import select
from fastapi import HTTPException
from app import zoho_connection as oauth
from app.models import Bill,PaymentVoucher,ZohoDelivery,ZohoLink,utcnow
from app.zoho_outbox import SetupNeeded,content,fingerprint,payload,event


class UnknownOutcome(Exception):pass
class RateLimited(Exception):pass
class Refused(Exception):pass


def cents(value):
    return int((Decimal(str(value))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))


class ZohoSender:
    def __init__(self,settings):
        from app.zoho_storage import database_mode
        if settings.data_environment!='official' or not database_mode(settings):raise SetupNeeded('wrong_environment')
        self.settings=settings;self.last=0;self.calls=0
        selected=(oauth.saved_record(settings).get('connection') or {}).get('organization')
        if not selected:raise SetupNeeded('write_access')
        self.organization=selected['id']

    def ready(self,kind):
        state=oauth.saved_record(self.settings).get('connection') or {}
        needed='ZohoBooks.'+('bills' if kind=='bill' else 'vendorpayments')+'.'
        if not self.settings.zoho_outbound_enabled:raise SetupNeeded('setup_disabled')
        if not {needed+'READ',needed+'CREATE'} <= set(state.get('scopes',oauth.SCOPES)):raise SetupNeeded('write_access')

    def request(self,method,path,params=None,body=None):
        oauth.require_network(self.settings)
        if not re.fullmatch(r'/(?:bills|vendorpayments|contacts|chartofaccounts|settings/taxes)(?:/[A-Za-z0-9_-]{1,80})?',path):
            raise SetupNeeded('mapping')
        if method not in ('GET','POST') or method=='POST' and path not in ('/bills','/vendorpayments'):raise Refused()
        if method=='POST':self.ready('bill' if path=='/bills' else 'vendor_payment')
        if self.calls>=40:raise RateLimited()
        with oauth.locked(self.settings) as state:
            connection=state.get('connection') or {}
            if (connection.get('organization') or {}).get('id')!=self.organization:raise SetupNeeded('write_access')
            if connection.get('expires',0)<=time.time()+60:oauth.refresh(self.settings,connection)
            from app.zoho_runtime import reserve
            reserve(self.settings,self.organization,self.settings.zoho_daily_limit)
            time.sleep(max(0,1.1-(time.monotonic()-self.last)));self.last=time.monotonic();self.calls+=1
            try:
                with httpx.Client(timeout=15,follow_redirects=False) as client:
                    response=client.request(method,oauth.REGIONS[self.settings.zoho_region][1]+'/books/v3'+path,
                        params={**(params or {}),'organization_id':self.organization},json=body,
                        headers={'Authorization':'Zoho-oauthtoken '+connection['access']})
            except httpx.HTTPError:
                if method=='POST':raise UnknownOutcome() from None
                raise RateLimited() from None
            if response.status_code==429:raise RateLimited()
            if response.status_code>=500:
                if method=='POST':raise UnknownOutcome()
                raise RateLimited()
            if response.status_code in (401,403):raise SetupNeeded('write_access')
            if response.status_code>=400:raise Refused()
            try:data=response.json()
            except ValueError:
                if method=='POST':raise UnknownOutcome() from None
                raise RateLimited() from None
            if not isinstance(data,dict) or data.get('code')!=0:raise Refused()
            return data

    def find(self,kind,reference):
        path='/bills' if kind=='bill' else '/vendorpayments';key='bills' if kind=='bill' else 'vendorpayments'
        data=self.request('GET',path,{'reference_number':reference,'per_page':200})
        if not isinstance(data.get(key),list):raise Refused()
        exact=[x for x in data[key] if x.get('reference_number')==reference]
        if len(exact)>1 or (data.get('page_context') or {}).get('has_more_page'):raise Refused()
        if not exact:return None
        identifier=str(exact[0].get('bill_id' if kind=='bill' else 'payment_id',''))
        return self.request('GET',path+'/'+identifier).get('bill' if kind=='bill' else 'vendorpayment')

    def validate(self,kind,body,snapshot):
        vendor=self.request('GET','/contacts/'+body['vendor_id']).get('contact') or {}
        if str(vendor.get('contact_id'))!=body['vendor_id'] or vendor.get('status')!='active' or vendor.get('currency_code')!=self.settings.org_currency:raise SetupNeeded('mapping')
        if kind=='bill':
            existing=self.request('GET','/bills',{'bill_number':body['bill_number'],'vendor_id':body['vendor_id'],'per_page':200})
            if any(x.get('bill_number')==body['bill_number'] and str(x.get('vendor_id'))==body['vendor_id'] for x in existing.get('bills',[])):
                raise SetupNeeded('existing_reference')
            if (existing.get('page_context') or {}).get('has_more_page'):raise SetupNeeded('existing_reference')
            for identifier in {x['account_id'] for x in body['line_items']}:
                account=self.request('GET','/chartofaccounts/'+identifier).get('chartofaccount') or {}
                if str(account.get('account_id'))!=identifier or account.get('is_active') is not True:raise SetupNeeded('mapping')
            # EWT treatment differs by edition. Never send an unverified TDS interpretation.
            if any(x.get('tds_tax_id') for x in body['line_items']):raise SetupNeeded('withholding_review')
            for item,source in zip(body['line_items'],snapshot['lines']):
                if source['vat']=='vat' and not item.get('tax_id'):raise SetupNeeded('mapping')
                if item.get('tax_id'):
                    tax=self.request('GET','/settings/taxes/'+item['tax_id']).get('tax') or {}
                    if str(tax.get('tax_id'))!=item['tax_id']:raise SetupNeeded('mapping')
                    expected=Decimal(snapshot['vatBp'])/100 if source['vat']=='vat' and snapshot.get('vatBp') is not None else Decimal(0)
                    if Decimal(str(tax.get('tax_percentage',-1)))!=expected:raise SetupNeeded('mapping')
        else:
            account=self.request('GET','/chartofaccounts/'+body['paid_through_account_id']).get('chartofaccount') or {}
            if str(account.get('account_id'))!=body['paid_through_account_id'] or account.get('is_active') is not True:raise SetupNeeded('mapping')
            for allocation,source in zip(body['bills'],snapshot['lines']):
                bill=self.request('GET','/bills/'+allocation['bill_id']).get('bill') or {}
                if str(bill.get('vendor_id'))!=body['vendor_id'] or bill.get('currency_code')!=self.settings.org_currency:
                    raise SetupNeeded('mapping')
                if cents(bill.get('balance',0))<cents(allocation['amount_applied']):raise SetupNeeded('existing_reference')
                if bill.get('bill_number')!=source['billNumber'] or bill.get('date')!=source['billDate'] or cents(bill.get('total',0))!=source['billTotal']:
                    raise SetupNeeded('mapping')

    def create(self,kind,body):
        result=self.request('POST','/bills' if kind=='bill' else '/vendorpayments',body=body)
        value=result.get('bill' if kind=='bill' else 'vendorpayment')
        if not isinstance(value,dict):raise UnknownOutcome()
        return value


def matches(job,body,remote):
    if not isinstance(remote,dict) or remote.get('reference_number')!=job.reference or str(remote.get('vendor_id'))!=body['vendor_id']:return False
    if remote.get('date')!=body['date']:return False
    for company in body.get('custom_fields',[]):
        if not any(str(field.get('custom_field_id') or field.get('field_id'))==company['custom_field_id'] and field.get('value')==company['value'] for field in remote.get('custom_fields',[])):
            return False
    try:
        if job.kind=='bill':
            return remote.get('bill_number')==body['bill_number'] and cents(remote.get('total'))==job.snapshot['total']
        expected={x['bill_id']:cents(x['amount_applied']) for x in body['bills']}
        actual={str(x['bill_id']):cents(x['amount_applied']) for x in remote.get('bills',[])}
        return cents(remote.get('amount'))==job.snapshot['amount'] and actual==expected
    except (ValueError,TypeError,KeyError,InvalidOperation):return False


def process(sessions,settings,job_id,sender,reconcile_only=False):
    with sessions() as db:
        job=db.get(ZohoDelivery,job_id)
        if not job or (not reconcile_only and job.status!='working'):return
        owner=job.owner
        if job.environment!='official' or settings.data_environment!='official':
            job.status='cancelled';job.error_code='wrong_environment';job.owner=None;job.lease_until=None;db.commit();return
        record=db.get(Bill if job.kind=='bill' else PaymentVoucher,job.local_id)
        if not record or record.status!=('recorded' if job.kind=='bill' else 'released') or fingerprint(content(job.kind,record,db))!=job.fingerprint:
            job.status='needs_attention';job.error_code='changed_record';job.owner=None;job.lease_until=None;event(db,job,'blocked',code=job.error_code);db.commit();return
        remote=None;identifier=None
        try:
            if record.zoho_ref and record.zoho_ref!=job.remote_id:raise SetupNeeded('existing_reference')
            if not reconcile_only:sender.ready(job.kind)
            if not job.organization_id or job.organization_id!=sender.organization:raise SetupNeeded('write_access')
            body=payload(db,job)
            remote=sender.find(job.kind,job.reference)
            if remote is None:
                if reconcile_only or job.attempts:
                    job.status='uncertain';job.error_code='unknown_outcome';db.commit();return
                sender.validate(job.kind,body,job.snapshot)
                # This marker commits before POST: a process death is an unknown outcome.
                job.attempts+=1;event(db,job,'sending');db.commit()
                remote=sender.create(job.kind,body)
            identifier=str(remote.get('bill_id' if job.kind=='bill' else 'payment_id',''))
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',identifier):raise UnknownOutcome()
            db.refresh(job)
            job.remote_id=identifier
            if job.owner!=owner or not matches(job,body,remote):
                job.remote_id=identifier;job.status='needs_attention';job.error_code='response_mismatch'
            else:
                job.remote_id=identifier;job.status='sent';job.error_code=None
                key=(job.organization_id,'bill' if job.kind=='bill' else 'vendor_payment',job.local_id)
                link=db.get(ZohoLink,key)
                if link and link.remote_id and link.remote_id!=identifier:raise Refused()
                if not link:db.add(ZohoLink(organization_id=key[0],kind=key[1],local_id=key[2],remote_id=identifier,confirmed=True,confirmed_by='Background verification'))
                record.zoho_ref=identifier
            event(db,job,job.status,code=job.error_code)
        except SetupNeeded as error:
            job.status='waiting_for_bill' if str(error)=='linked_bill' else 'waiting_for_setup';job.error_code=str(error)
            job.next_attempt=utcnow()+timedelta(minutes=15);event(db,job,'blocked',code=job.error_code)
        except RateLimited:
            job.status='needs_attention' if job.attempts>=5 else 'waiting_to_send';job.error_code='rate_limit';job.next_attempt=utcnow()+timedelta(minutes=15)
            event(db,job,'retry_scheduled',code=job.error_code)
        except UnknownOutcome:
            job.status='uncertain';job.error_code='unknown_outcome';event(db,job,'uncertain',code=job.error_code)
        except Refused:
            job.status='needs_attention';job.error_code='provider_validation';event(db,job,'refused',code=job.error_code)
        except HTTPException:
            job.status='waiting_to_send';job.error_code='rate_limit';job.next_attempt=utcnow()+timedelta(minutes=15)
        except Exception:
            job.status='uncertain' if job.attempts else 'needs_attention';job.error_code='worker_error'
            if identifier:job.remote_id=identifier
            event(db,job,'worker_error',code=job.error_code)
        finally:
            job.owner=None;job.lease_until=None;job.updated_at=utcnow();db.commit()
