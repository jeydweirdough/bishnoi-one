"""Local Sales Orders: permission-gated approval, no invoice/stock/Zoho writes."""
from datetime import date
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import Field
from sqlalchemy import select, func, text
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import IntegrityError
from app.access import access_of, permitted
from app.audit import audit
from app.deps import DB, SettingsDep
from app.models import SalesOrder, utcnow
from app.notify import holders, tell, done
from app.routers.tax import Api, LineBody, SaleBody, BuyerBody, work_out, split_tin
from app.tax.packs.ph import categories

router=APIRouter(prefix='/sales-orders',tags=['sales orders'])
STATES={'draft':'Draft','submitted':'Waiting for approval','returned':'Returned','approved':'Approved in Finance','cancelled':'Cancelled'}

class OrderIn(Api):
    version:int=Field(1,ge=1)
    customer_name:str=Field(min_length=1,max_length=200)
    customer_tin:str|None=Field(None,max_length=20)
    customer_address:str|None=Field(None,max_length=300)
    order_date:date
    reference:str|None=Field(None,max_length=80)
    salesperson:str|None=Field(None,max_length=120)
    terms_days:int=Field(30,ge=0,le=365)
    prices_include_tax:bool=True
    notes:str|None=Field(None,max_length=1000)
    lines:list[LineBody]=Field(min_length=1,max_length=100)

class StepIn(Api):
    version:int=Field(ge=1)
    reason:str|None=Field(None,max_length=300)

def prepared(order,user):
    return order.created_by_id==user.id or order.submitted_by_id==user.id or any(event['userId']==user.id and event['kind']=='edited' for event in order.events)

def permissions(order,user):
    can=access_of(user).can
    editable=order.status in ('draft','returned')
    approvable=order.status=='submitted' and not prepared(order,user)
    return {'canEdit':editable and can('sales_orders.create'),'canSubmit':editable and can('sales_orders.submit'),
            'canApprove':approvable and can('sales_orders.approve'),'canReturn':approvable and can('sales_orders.approve'),
            'canCancel':order.status!='cancelled' and can('sales_orders.cancel')}

def output(order,user):
    return {'id':order.id,'number':order.number,'status':order.status,'statusLabel':STATES[order.status],'version':order.version,
            'customerName':order.customer_name,'customerTin':order.customer_tin,'customerAddress':order.customer_address,
            'date':order.order_date.isoformat(),'reference':order.reference,'salesperson':order.salesperson,'termsDays':order.terms_days,
            'pricesIncludeTax':order.prices_include_tax,'notes':order.notes,'lines':order.lines,'totalCentavos':order.total_centavos,
            'taxCentavos':order.tax_centavos,'createdBy':order.created_by,'events':order.events,
            'zohoStatus':'Not connected — local approval only',**permissions(order,user)}

def found(db,order_id):
    order=db.get(SalesOrder,order_id)
    if not order:raise HTTPException(404,'Sales order not found.')
    return order

def event(order,user,kind,reason=None):
    order.updated_at=utcnow()
    order.events=[*(order.events or []),{'kind':kind,'who':user.full_name,'userId':user.id,'at':order.updated_at.isoformat(),'reason':reason}]

def save(db):
    try:db.commit()
    except (StaleDataError,IntegrityError):
        db.rollback()
        raise HTTPException(409,'This order changed while you were working. Reload before trying again.') from None

def flush(db):
    try:db.flush()
    except (StaleDataError,IntegrityError):
        db.rollback()
        raise HTTPException(409,'This order changed while you were working. Reload before trying again.') from None

def apply(db,settings,order,body):
    if any(not (line.description or line.ref) for line in body.lines):raise HTTPException(422,'Give every line an item description or reference.')
    if body.customer_tin:
        try:split_tin(body.customer_tin)
        except ValueError as error:raise HTTPException(422,str(error)) from None
    computed=work_out(db,settings,SaleBody(on=body.order_date,prices_include_tax=body.prices_include_tax,
                        buyer=BuyerBody(name=body.customer_name,tin=body.customer_tin,address=body.customer_address),lines=body.lines))
    if computed['totalDueCentavos']<=0:raise HTTPException(422,'The order total must be greater than zero.')
    for key in ('customer_name','customer_tin','customer_address','order_date','reference','salesperson','terms_days','prices_include_tax','notes'):
        setattr(order,key,getattr(body,key))
    order.lines=[line.model_dump(by_alias=True) for line in body.lines]
    order.total_centavos=computed['totalDueCentavos']
    order.tax_centavos=next((line['amountCentavos'] for line in computed['summary'] if line['key']=='tax'),0)

@router.get('')
def listing(user:permitted('sales_orders.view'),db:DB,q:str='',queue:Literal['all','to_approve','waiting','mine','returned']='all'):
    rows=list(db.scalars(select(SalesOrder).order_by(SalesOrder.updated_at.desc())))
    pending=[o for o in rows if permissions(o,user)['canApprove']]
    waiting=[o for o in rows if o.status=='submitted' and prepared(o,user)]
    counts={'toApprove':len(pending),'waiting':len(waiting),'returned':sum(o.status=='returned' for o in rows)}
    if queue=='to_approve':rows=pending
    elif queue=='waiting':rows=waiting
    elif queue=='mine':rows=[o for o in rows if prepared(o,user)]
    elif queue=='returned':rows=[o for o in rows if o.status=='returned']
    if q:rows=[o for o in rows if q.casefold() in f'{o.number} {o.customer_name} {o.reference or ""}'.casefold()]
    return {'items':[output(o,user) for o in rows],'counts':counts,'canCreate':access_of(user).can('sales_orders.create'),
            'categories':[{'key':key,'name':name} for key,name in categories.items()]}

@router.post('',status_code=201)
def create(user:permitted('sales_orders.create'),db:DB,settings:SettingsDep,body:OrderIn):
    # Serialise number allocation, including an empty table, without modifying rows.
    db.execute(text('LOCK TABLE nbfi_sales_orders IN SHARE ROW EXCLUSIVE MODE') if db.get_bind().dialect.name=='postgresql' else text('UPDATE nbfi_sales_orders SET version=version WHERE 1=0'))
    prefix=f'SO-{body.order_date:%Y%m}-'
    last=db.scalar(select(func.max(SalesOrder.number)).where(SalesOrder.number.like(prefix+'%')))
    number=prefix+f'{int(last.rsplit("-",1)[1])+1 if last else 1:06d}'
    order=SalesOrder(number=number,created_by_id=user.id,created_by=user.full_name,status='draft',events=[])
    apply(db,settings,order,body);event(order,user,'created');db.add(order);db.flush()
    audit(db,user,'sales_order.created',target=number,target_type='sales_order',target_id=order.id)
    save(db);return output(order,user)

@router.get('/{order_id}')
def read(order_id:str,user:permitted('sales_orders.view'),db:DB):return output(found(db,order_id),user)

@router.put('/{order_id}')
def edit(order_id:str,user:permitted('sales_orders.create'),db:DB,settings:SettingsDep,body:OrderIn):
    order=found(db,order_id)
    if body.version!=order.version or order.status not in ('draft','returned'):raise HTTPException(409,'Only a current draft or returned order can be edited. Reload first.')
    apply(db,settings,order,body);event(order,user,'edited')
    audit(db,user,'sales_order.edited',target=order.number,target_type='sales_order',target_id=order.id)
    save(db);return output(order,user)

def transition(order_id,user,db,body,action):
    order=found(db,order_id)
    if order.version!=body.version:raise HTTPException(409,'This order has changed. Reload before acting.')
    allowed={'submit':'canSubmit','approve':'canApprove','return':'canReturn','cancel':'canCancel'}
    if action in ('approve','return') and prepared(order,user):raise HTTPException(403,'You prepared or submitted this order; someone else must approve or return it.')
    if not permissions(order,user)[allowed[action]]:raise HTTPException(409,'This action is not available in the current state.')
    reason=(body.reason or '').strip()
    if action in ('return','cancel') and len(reason)<3:raise HTTPException(422,'Give a reason in a few words.')
    order.status={'submit':'submitted','approve':'approved','return':'returned','cancel':'cancelled'}[action]
    if action=='submit':order.submitted_by_id=user.id
    event(order,user,{'submit':'submitted','approve':'approved','return':'returned','cancel':'cancelled'}[action],reason or None)
    flush(db)  # Check the optimistic version before notification queries autoflush.
    link=f'/sales-orders/{order.id}'
    done(db,'sales_order.to_approve',link)
    if action=='submit':
        done(db,'sales_order.returned',link)
        tell(db,[person for person in holders(db,'sales_orders.approve') if not prepared(order,person)],'sales_order.to_approve',f'{order.number} for {order.customer_name} is waiting for approval in Finance.',link=link)
    else:
        tell(db,[order.created_by_id,order.submitted_by_id],f'sales_order.{order.status}',f'{order.number} was {order.status} by {user.full_name}'+(f': {reason}' if reason else ''),link=link,not_to=[user.id])
    audit(db,user,f'sales_order.{order.status}',target=order.number,target_type='sales_order',target_id=order.id)
    save(db);return output(order,user)

@router.post('/{order_id}/submit')
def submit(order_id:str,user:permitted('sales_orders.submit'),db:DB,body:StepIn):return transition(order_id,user,db,body,'submit')
@router.post('/{order_id}/approve')
def approve(order_id:str,user:permitted('sales_orders.approve'),db:DB,body:StepIn):return transition(order_id,user,db,body,'approve')
@router.post('/{order_id}/return')
def returned(order_id:str,user:permitted('sales_orders.approve'),db:DB,body:StepIn):return transition(order_id,user,db,body,'return')
@router.post('/{order_id}/cancel')
def cancel(order_id:str,user:permitted('sales_orders.cancel'),db:DB,body:StepIn):return transition(order_id,user,db,body,'cancel')
