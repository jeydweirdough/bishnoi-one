"""Received purchase evidence. Receipt intake never posts stock, accounting or money."""
from datetime import datetime, timezone
import hashlib
import json
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, select,func
from sqlalchemy.orm import Mapped, mapped_column

from modules.finance import company_scope
from modules.finance.access import access_of, permitted
from modules.finance.audit import audit
from modules.finance.db import Base
from modules.finance.deps import DB, SettingsDep
from modules.finance.locks import begin_change,lock_series
from modules.finance.models import Bill, Supplier


def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)


class PurchaseIntake(Base):
    __tablename__ = 'nbfi_purchase_intakes'
    __table_args__ = (UniqueConstraint('company', 'receipt_id', name='purchase_intake_source_once'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company: Mapped[str] = mapped_column(String(40))
    receipt_id: Mapped[str] = mapped_column(String(36))
    handoff_id: Mapped[str] = mapped_column(String(36), unique=True)
    digest: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    reason: Mapped[str | None] = mapped_column(String(300), default=None)
    source_conflict: Mapped[bool] = mapped_column(Boolean,default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PurchaseSupplierLink(Base):
    __tablename__ = 'nbfi_purchase_supplier_links'
    company: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_supplier_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey('nbfi_suppliers.id'))
    reviewed_by: Mapped[str] = mapped_column(String(120))
    evidence: Mapped[str] = mapped_column(String(300))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PurchaseAllocation(Base):
    __tablename__ = 'nbfi_purchase_allocations'
    __table_args__ = (UniqueConstraint('bill_id', 'position', name='purchase_bill_line_once'),CheckConstraint('quantity > 0',name='purchase_allocation_positive'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    intake_id: Mapped[str] = mapped_column(ForeignKey('nbfi_purchase_intakes.id'))
    source_line_id: Mapped[str] = mapped_column(String(36))
    quantity: Mapped[int] = mapped_column(Integer)
    bill_id: Mapped[str] = mapped_column(ForeignKey('nbfi_bills.id'))
    position: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Preparation(Base):
    __tablename__ = 'nbfi_purchase_preparations'
    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    digest: Mapped[str] = mapped_column(String(64))
    invoice_key: Mapped[str|None] = mapped_column(String(64),unique=True,default=None)
    bill_id: Mapped[str] = mapped_column(ForeignKey('nbfi_bills.id'))


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class SourceLine(Strict):
    id: str = Field(min_length=1,max_length=36)
    orderLineId: str = Field(min_length=1,max_length=36)
    productId: str = Field(min_length=1,max_length=36)
    unitCode: str = Field(min_length=1,max_length=16)
    product: str = Field(min_length=1,max_length=200)
    unit: str = Field(min_length=1,max_length=80)
    quantity: int = Field(gt=0,le=10**9)
    unitCost: int = Field(ge=0,le=10**11)


class ReceiptEvidence(Strict):
    schemaVersion: int = Field(ge=1,le=1)
    handoffId: str = Field(min_length=1,max_length=36)
    receiptId: str = Field(min_length=1,max_length=36)
    receiptNumber: str = Field(min_length=1,max_length=60)
    orderId: str = Field(min_length=1,max_length=36)
    orderNumber: str = Field(min_length=1,max_length=60)
    supplierId: str = Field(min_length=1,max_length=36)
    supplierName: str = Field(min_length=1,max_length=200)
    supplierTin: str | None = Field(default=None,max_length=40)
    currencyEvidence: str = Field(min_length=3,max_length=3)
    deliveryRef: str | None = Field(default=None,max_length=60)
    receivedAt: str = Field(min_length=1,max_length=40)
    receivedBy: str = Field(min_length=1,max_length=120)
    qualityReady: bool
    lines: list[SourceLine] = Field(min_length=1,max_length=200)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def supplier_for(db,item):
    link=db.get(PurchaseSupplierLink,('2mg',item.snapshot['supplierId']))
    s=db.get(Supplier,link.supplier_id) if link else None
    return s if s and s.is_active and company_scope.scope_for(db,'supplier',s.id)=='2mg' else None


def allocations(db,item):
    return list(db.scalars(select(PurchaseAllocation).where(PurchaseAllocation.intake_id==item.id)))


def out(db,item):
    rows=allocations(db,item);used={}
    for a in rows:
        if a.active:used[a.source_line_id]=used.get(a.source_line_id,0)+a.quantity
    s=supplier_for(db,item)
    holds=[]
    if not s:holds.append('Link this Inventory vendor to an active Finance supplier.')
    if not item.snapshot['qualityReady']:holds.append('Receiving quality/accepted quantities need review.')
    if item.snapshot['currencyEvidence']!='PHP':holds.append('Only PHP bills are supported. Review foreign source evidence separately.')
    if item.reason:holds.append(item.reason)
    remaining=sum(ln['quantity']-used.get(ln['id'],0) for ln in item.snapshot['lines'])
    state='needs_correction' if item.reason else 'held' if holds else 'allocated' if remaining==0 else 'partially_allocated' if used else 'received'
    bills=[]
    for bid in sorted({a.bill_id for a in rows}):
        b=db.get(Bill,bid)
        if b:bills.append({'id':b.id,'number':b.bill_number,'state':b.stage or b.status})
    return {'id':item.id,'version':item.version,'state':state,'holds':holds,'snapshot':item.snapshot,'sourceConflict':item.source_conflict,
        'supplier':{'id':s.id,'name':s.name} if s else None,'remaining':remaining,'bills':bills,
        'lines':[ln|{'allocated':used.get(ln['id'],0),'remaining':ln['quantity']-used.get(ln['id'],0)} for ln in item.snapshot['lines']]}


def reply(db,item):
    from modules.finance.business_events import emit
    detail=out(db,item)
    from modules.finance.models import Notification
    from modules.finance.notify import done,holders,tell
    link='/purchase-intakes/'+item.id
    if detail['remaining']==0:done(db,'purchase.received',link)
    elif not db.scalar(select(Notification.id).where(Notification.kind=='purchase.received',Notification.link==link,Notification.read_at.is_(None)).limit(1)):
        tell(db,holders(db,'bills.create'),'purchase.received','A received purchase needs Finance attention; open it to see the next owner.',link=link)
    emit(db,None,'purchase.receipt_finance_updated',{'schemaVersion':1,'handoffId':item.handoff_id,
        'receiptId':item.receipt_id,'digest':item.digest,'version':item.version,'state':detail['state'],
        'remaining':detail['remaining'],'reason':item.reason or (detail['holds'][0] if detail['holds'] else None),
        'bills':[{'id':b['id'],'state':b['state']} for b in detail['bills']]})


def receive(db,data,slug):
    try: body=ReceiptEvidence.model_validate(data)
    except ValueError:raise HTTPException(422,'Invalid purchase receipt contract; no bill was created.') from None
    snapshot=body.model_dump();ids=[ln.id for ln in body.lines]
    if len(set(ids))!=len(ids):raise HTTPException(422,'A received line appears twice.')
    begin_change(db)
    item=db.scalar(select(PurchaseIntake).where(PurchaseIntake.company=='2mg',PurchaseIntake.receipt_id==body.receiptId).with_for_update())
    if item:
        if item.digest!=digest(snapshot) or item.handoff_id!=body.handoffId:
            # Do not overwrite submitted or approved evidence from a later source payload.
            item.reason='Received evidence changed. Review the source correction before preparing or submitting more work.'
            item.source_conflict=True
            item.version+=1;db.flush();reply(db,item);return
        reply(db,item);return
    if db.scalar(select(PurchaseIntake.id).where(PurchaseIntake.handoff_id==body.handoffId)):
        raise HTTPException(409,'This handoff ID already belongs to another receipt.')
    item=PurchaseIntake(company='2mg',receipt_id=body.receiptId,handoff_id=body.handoffId,
        digest=digest(snapshot),snapshot=snapshot)
    db.add(item);db.flush();reply(db,item)


def linked(db,bill_id):
    return list(db.scalars(select(PurchaseAllocation).where(PurchaseAllocation.bill_id==bill_id,PurchaseAllocation.active)))


def guard_bill(db,bill,*,lock=True):
    rows=linked(db,bill.id)
    if not rows:return
    for item_id in sorted({a.intake_id for a in rows}):
        query=select(PurchaseIntake).where(PurchaseIntake.id==item_id)
        item=db.scalar(query.with_for_update() if lock else query)
        if item.reason or not item.snapshot['qualityReady'] or not supplier_for(db,item) or supplier_for(db,item).id!=bill.supplier_id:
            raise HTTPException(409,'This received purchase needs source/supplier review before proceeding.')
    if len(bill.lines)!=len(rows):raise HTTPException(409,'Keep source-linked bill lines with their received-quantity allocations.')


def evidence_for(db,bill_id,*,include_inactive=False):
    rows=list(db.scalars(select(PurchaseAllocation).where(PurchaseAllocation.bill_id==bill_id))) if include_inactive else linked(db,bill_id)
    return [{'intakeId':a.intake_id,'sourceLineId':a.source_line_id,'quantity':a.quantity,
        'position':a.position,'active':a.active,'digest':db.get(PurchaseIntake,a.intake_id).digest}
        for a in sorted(rows,key=lambda a:a.position)]


def updated_bill(db,bill):
    for iid in sorted({a.intake_id for a in linked(db,bill.id)}):
        item=db.get(PurchaseIntake,iid);item.version+=1;db.flush();reply(db,item)


def protect_bill(db,bill_id):
    if db.scalar(select(PurchaseAllocation.id).where(PurchaseAllocation.bill_id==bill_id).limit(1)):
        raise HTTPException(409,'This bill has received-purchase evidence. Use its audited cancellation/void flow; do not delete its links.')


router=APIRouter(prefix='/finance/purchase-intakes',tags=['Received purchases'])


def found(db,id):
    item=db.get(PurchaseIntake,id)
    if not item:raise HTTPException(404,'No such received purchase.')
    return item


@router.get('')
def listing(user:permitted('bills.view'),db:DB,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    rows=list(db.scalars(select(PurchaseIntake).order_by(PurchaseIntake.received_at.desc(),PurchaseIntake.id).offset(offset).limit(limit)))
    return {'items':[out(db,x) for x in rows],'total':db.scalar(select(func.count()).select_from(PurchaseIntake)),
        'limit':limit,'offset':offset,'canPrepare':access_of(user).can('bills.create'),'canLinkSupplier':access_of(user).can('suppliers.edit')}


@router.get('/{id}')
def read(id:str,user:permitted('bills.view'),db:DB):
    return out(db,found(db,id))|{'canPrepare':access_of(user).can('bills.create'),'canLinkSupplier':access_of(user).can('suppliers.edit')}


class SupplierLinkIn(Strict):
    version:int
    supplierId:str=Field(min_length=1,max_length=36)
    evidence:str=Field(min_length=3,max_length=300)


@router.post('/{id}/supplier')
def link_supplier(id:str,body:SupplierLinkIn,user:permitted('suppliers.edit'),db:DB):
    access_of(user).require('bills.view')
    begin_change(db);item=found(db,id)
    if item.version!=body.version:raise HTTPException(409,'This receipt changed. Reload before linking its supplier.')
    company_scope.require_ids(db,'supplier',[body.supplierId])
    s=db.get(Supplier,body.supplierId)
    if not s or not s.is_active:raise HTTPException(422,'Choose an active Finance supplier.')
    key=('2mg',item.snapshot['supplierId']);old=db.get(PurchaseSupplierLink,key)
    if old and old.supplier_id!=s.id:raise HTTPException(409,'This source vendor is already linked. A reviewed crosswalk correction is required.')
    if not old:db.add(PurchaseSupplierLink(company='2mg',source_supplier_id=key[1],supplier_id=s.id,reviewed_by=user.full_name,evidence=body.evidence))
    db.flush()
    affected=db.scalars(select(PurchaseIntake).where(PurchaseIntake.company=='2mg').order_by(PurchaseIntake.id).with_for_update()).all()
    for row in affected:
        if row.snapshot['supplierId']==key[1]:row.version+=1;db.flush();reply(db,row)
    audit(db,user,'purchase.supplier_linked',target='Reviewed received-purchase vendor',target_type='purchase_intake',target_id=item.id)
    db.commit();return out(db,item)


class ReturnIn(Strict):
    version:int
    reason:str=Field(min_length=3,max_length=300)


@router.post('/{id}/return')
def return_source(id:str,body:ReturnIn,user:permitted('bills.create'),db:DB):
    access_of(user).require('bills.view')
    begin_change(db);item=found(db,id)
    if item.version!=body.version:raise HTTPException(409,'This receipt changed. Reload first.')
    item.reason=body.reason;item.version+=1;db.flush();reply(db,item)
    audit(db,user,'purchase.returned',target='Receiving evidence needs correction',target_type='purchase_intake',target_id=item.id)
    db.commit();return out(db,item)


@router.post('/{id}/resume')
def resume_source(id:str,body:ReturnIn,user:permitted('bills.create'),db:DB):
    access_of(user).require('bills.view')
    begin_change(db);item=found(db,id)
    if item.version!=body.version:raise HTTPException(409,'This receipt changed. Reload first.')
    if item.source_conflict or not item.snapshot['qualityReady']:
        raise HTTPException(409,'Changed or quality-held receiving evidence cannot be cleared by a Finance note.')
    if not item.reason:raise HTTPException(409,'This receipt has no receiving-correction hold.')
    item.reason=None;item.version+=1;db.flush();reply(db,item)
    audit(db,user,'purchase.review_resumed',target=body.reason,target_type='purchase_intake',target_id=item.id)
    db.commit();return out(db,item)


class AllocationIn(Strict):
    intakeId:str
    sourceLineId:str
    quantity:int=Field(gt=0,le=10**9)
    version:int


class PrepareIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    requestId:str=Field(min_length=36,max_length=36)
    sourceReviewed:bool
    allocations:list[AllocationIn]=Field(min_length=1,max_length=100)
    bill:dict


@router.post('/prepare',status_code=201)
def prepare(body:PrepareIn,user:permitted('bills.create'),db:DB,settings:SettingsDep):
    access_of(user).require('bills.view')
    from modules.finance.routers.payables import BillIn,apply_bill,bill_out
    begin_change(db);fingerprint=digest(body.model_dump())
    prior=db.get(Preparation,body.requestId)
    if prior:
        if prior.digest!=fingerprint:raise HTTPException(409,'This preparation key was already used for different work.')
        return bill_out(db,db.get(Bill,prior.bill_id),user)
    if not body.sourceReviewed:raise HTTPException(422,'Confirm invoice quantities, unit/currency/price basis and source evidence first.')
    try:body_bill=BillIn.model_validate(body.bill)
    except ValueError:raise HTTPException(422,'Complete the supplier invoice, dates, account and line tax fields before preparing the bill.') from None
    invoice_key=digest({'supplier':body_bill.supplier_id,'number':body_bill.bill_number.strip().casefold(),'date':body_bill.bill_date.isoformat()})
    lock_series(db,'purchase-invoice:'+invoice_key)
    # Different browser retries/encoders must not prepare the same invoice twice.
    prior=db.get(Preparation,body.requestId)
    if prior:
        if prior.digest!=fingerprint:raise HTTPException(409,'This preparation key was already used for different work.')
        return bill_out(db,db.get(Bill,prior.bill_id),user)
    if db.scalar(select(Preparation.request_id).where(Preparation.invoice_key==invoice_key)):
        raise HTTPException(409,'This supplier invoice already has a prepared bill. Open that bill instead of preparing it again.')
    if len(body.allocations)!=len(body_bill.lines):raise HTTPException(422,'Each bill line needs one explicit received-quantity allocation.')
    ids=sorted({a.intakeId for a in body.allocations})
    items={x.id:x for x in db.scalars(select(PurchaseIntake).where(PurchaseIntake.id.in_(ids)).order_by(PurchaseIntake.id).with_for_update())}
    wanted={}
    for a in body.allocations:
        item=items.get(a.intakeId)
        if not item or item.version!=a.version:raise HTTPException(409,'Receiving evidence changed; reload the selected receipts.')
        if item.reason or not item.snapshot['qualityReady']:raise HTTPException(409,'Resolve the receiving/quality hold first.')
        s=supplier_for(db,item)
        if not s or s.id!=body_bill.supplier_id:raise HTTPException(409,'Every received line must belong to this verified supplier.')
        if item.snapshot['currencyEvidence']!='PHP':
            raise HTTPException(409,'Receipt currency evidence differs from the invoice. Resolve the source pricing/currency review first.')
        line=next((ln for ln in item.snapshot['lines'] if ln['id']==a.sourceLineId),None)
        if not line:raise HTTPException(422,'A selected line is not on this receipt.')
        key=(a.intakeId,a.sourceLineId);wanted[key]=wanted.get(key,0)+a.quantity
        used=sum(x.quantity for x in allocations(db,item) if x.active and x.source_line_id==a.sourceLineId)
        if used+wanted[key]>line['quantity']:raise HTTPException(409,'This exceeds the received quantity still available for a bill.')
    b=Bill(created_by=user.full_name);apply_bill(db,settings,b,body_bill,user);db.add(b);db.flush()
    for pos,a in enumerate(body.allocations):db.add(PurchaseAllocation(intake_id=a.intakeId,source_line_id=a.sourceLineId,quantity=a.quantity,bill_id=b.id,position=pos))
    db.add(Preparation(request_id=body.requestId,digest=fingerprint,invoice_key=invoice_key,bill_id=b.id));db.flush()
    for item in items.values():item.version+=1;db.flush();reply(db,item)
    from modules.finance.business_events import link,ref
    for item in items.values():link(db,None,ref('receipt',item.receipt_id,item.snapshot['receiptNumber'],'inventory'),ref('bill',b.id,b.bill_number))
    audit(db,user,'purchase.bill_prepared',target='Draft bill from received quantities',target_type='bill',target_id=b.id)
    db.commit();return bill_out(db,b,user)


@router.post('/bills/{bill_id}/cancel-draft')
def cancel_draft(bill_id:str,user:permitted('bills.create'),db:DB):
    begin_change(db);b=db.scalar(select(Bill).where(Bill.id==bill_id).with_for_update())
    if not b:raise HTTPException(404,'No such bill.')
    rows=linked(db,b.id)
    if not rows:raise HTTPException(409,'No active received-purchase allocations.')
    if b.status!='draft' or b.stage not in (None,'returned') or b.entry_id:raise HTTPException(409,'Only an unsubmitted draft can release its received-quantity allocations.')
    b.status='void';b.stage=None;b.voided_by=user.full_name;b.voided_at=now();b.void_reason='Cancelled unsubmitted received-purchase draft'
    for a in rows:a.active=False
    for prepared in db.scalars(select(Preparation).where(Preparation.bill_id==b.id)):prepared.invoice_key=None
    db.flush()
    for iid in sorted({a.intake_id for a in rows}):item=db.get(PurchaseIntake,iid);item.version+=1;db.flush();reply(db,item)
    audit(db,user,'purchase.draft_cancelled',target='Draft allocations released',target_type='bill',target_id=b.id)
    db.commit();return {'cancelled':True}
