"""Explicit receipt handoff. Does not receive stock or grant Finance authority."""
from datetime import datetime,timezone
import hashlib,json,uuid

from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import DateTime,ForeignKey,Integer,JSON,String,select,text
from sqlalchemy.orm import Mapped,mapped_column

from modules.inventory.access import allowed
from modules.inventory.audit import audit
from modules.inventory.db import Base
from modules.inventory.deps import DB,SettingsDep,CurrentUser
from modules.inventory.models import Receipt,QualityCheck,PurchaseOrder


class ReceiptHandoff(Base):
    __tablename__='nbin_receipt_finance_handoffs'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    receipt_id:Mapped[str]=mapped_column(ForeignKey('nbin_receipts.id'),unique=True)
    supplier_id:Mapped[str]=mapped_column(ForeignKey('nbin_suppliers.id'))
    order_id:Mapped[str]=mapped_column(ForeignKey('nbin_purchase_orders.id'))
    digest:Mapped[str]=mapped_column(String(64))
    snapshot:Mapped[dict]=mapped_column(JSON)
    sent_by:Mapped[str]=mapped_column(String(120))
    sent_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    state:Mapped[str]=mapped_column(String(40),default='sending')
    version:Mapped[int]=mapped_column(Integer,default=0)
    reason:Mapped[str|None]=mapped_column(String(300),default=None)
    remaining:Mapped[int]=mapped_column(Integer,default=0)
    bills:Mapped[list]=mapped_column(JSON,default=list)


def begin(db):
    if db.get_bind().dialect.name=='postgresql':db.execute(text("SET LOCAL lock_timeout = '10s'"))
    else:
        with db.no_autoflush:
            if not db.connection().connection.dbapi_connection.in_transaction:db.execute(text('BEGIN IMMEDIATE'))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def snapshot(db,r,handoff_id):
    check=db.scalar(select(QualityCheck).where(QualityCheck.receipt_id==r.id))
    return {'schemaVersion':1,'handoffId':handoff_id,'receiptId':r.id,'receiptNumber':r.number,
        'orderId':r.order_id,'orderNumber':r.order.number if r.order else '',
        'supplierId':r.supplier_id,'supplierName':r.supplier.name if r.supplier else '',
        'supplierTin':r.supplier.tin if r.supplier else None,
        'currencyEvidence':r.supplier.currency if r.supplier else 'PHP','deliveryRef':r.delivery_ref,
        'receivedAt':r.received_at.isoformat(),'receivedBy':r.received_by.full_name if r.received_by else 'Receiving record',
        'qualityReady':not check or check.status=='done',
        'lines':[{'id':ln.id,'orderLineId':ln.order_line_id,'productId':ln.product_id,'product':ln.product.name,
            'unitCode':ln.product.unit.code,'unit':ln.product.unit.name,'quantity':ln.quantity,'unitCost':ln.unit_cost} for ln in sorted(r.lines,key=lambda ln:ln.id)]}


def existing(db,r):
    return db.scalar(select(ReceiptHandoff).where(ReceiptHandoff.receipt_id==r.id))


def reason(db,r,settings):
    if not r.order_id or not r.supplier_id:return 'This action is for supplier deliveries against a purchase order.'
    if r.consignment:return 'Consignment is billed through its separate settlement flow.'
    check=db.scalar(select(QualityCheck).where(QualityCheck.receipt_id==r.id))
    if check and check.status!='done':return 'Quality checking is pending. Accepted quantities must be settled before this ordinary bill handoff.'
    if any(not ln.order_line_id for ln in r.lines):return 'Receiving evidence needs a purchase-order line for every received line.'
    return None


def projection(db,r,settings,can_send=False):
    h=existing(db,r);problem=reason(db,r,settings)
    return {'state':h.state if h else 'not_sent','reason':h.reason if h and h.reason else problem,
        'canSend':can_send and not problem,'digest':h.digest if h else None,
        'version':h.version if h else 0,'remaining':h.remaining if h else sum(ln.quantity for ln in r.lines),
        'bills':h.bills if h else [],'sentAt':h.sent_at.isoformat() if h else None,
        'sentBy':h.sent_by if h else None}


def protect(db,kind,id):
    col={'receipt':ReceiptHandoff.receipt_id,'supplier':ReceiptHandoff.supplier_id,'purchase_order':ReceiptHandoff.order_id}[kind]
    if db.scalar(select(ReceiptHandoff.id).where(col==id).limit(1)):
        raise HTTPException(409,'This record is linked to a Finance handoff. Keep its received evidence; use a reviewed correction instead of deleting it.')


def accept_status(db,data,slug):
    try:body=Reply.model_validate(data)
    except ValueError:raise HTTPException(422,'Invalid Finance status reply.') from None
    begin(db)
    h=db.scalar(select(ReceiptHandoff).where(ReceiptHandoff.id==body.handoffId).with_for_update())
    if not h or h.receipt_id!=body.receiptId or h.digest!=body.digest:raise HTTPException(409,'Finance reply does not match a saved receipt handoff.')
    if body.version<=h.version:return
    h.version=body.version;h.state=body.state;h.remaining=body.remaining;h.reason=body.reason
    h.bills=[b.model_dump() for b in body.bills]


class BillRef(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    id:str=Field(min_length=1,max_length=36)
    state:str=Field(min_length=1,max_length=40)


class Reply(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    schemaVersion:int=Field(ge=1,le=1)
    handoffId:str=Field(min_length=1,max_length=36)
    receiptId:str=Field(min_length=1,max_length=36)
    digest:str=Field(min_length=64,max_length=64)
    version:int=Field(ge=1)
    state:str=Field(pattern='^(received|held|needs_correction|partially_allocated|allocated)$')
    remaining:int=Field(ge=0)
    reason:str|None=Field(default=None,max_length=300)
    bills:list[BillRef]=Field(max_length=200)


router=APIRouter(prefix='/inventory/receipts',tags=['Receipt Finance handoff'])


@router.post('/{receipt_id}/finance-handoff')
def send(receipt_id:str,_:allowed('receiving.send_to_finance'),me:CurrentUser,db:DB,settings:SettingsDep):
    from modules.inventory.business_events import emit,OutboxEvent
    begin(db)
    r=db.scalar(select(Receipt).where(Receipt.id==receipt_id).with_for_update(of=Receipt))
    if not r:raise HTTPException(404,'No such receipt.')
    problem=reason(db,r,settings)
    if problem:raise HTTPException(409,problem)
    h=existing(db,r)
    if h:
        if fingerprint(snapshot(db,r,h.id))!=h.digest:raise HTTPException(409,'Source evidence changed after sending. Review the receiving correction; do not send a duplicate.')
        # Ask the existing durable outbox to retry; never create another handoff.
        pending=db.scalar(select(OutboxEvent.id).where(OutboxEvent.kind=='purchase.receipt_submitted',OutboxEvent.sent_at.is_(None)))
        if pending:db.info['events_out']=True
        db.commit();return projection(db,r,settings,True)
    handoff_id=str(uuid.uuid4());data=snapshot(db,r,handoff_id)
    h=ReceiptHandoff(id=handoff_id,receipt_id=r.id,supplier_id=r.supplier_id,order_id=r.order_id,
        digest=fingerprint(data),snapshot=data,sent_by=me.full_name,remaining=sum(ln.quantity for ln in r.lines))
    db.add(h);emit(db,settings.company,'purchase.receipt_submitted',data)
    audit(db,me,'receipt.sent_to_finance',target=r.number,target_type='receipt',target_id=r.id)
    db.commit();return projection(db,r,settings,True)
