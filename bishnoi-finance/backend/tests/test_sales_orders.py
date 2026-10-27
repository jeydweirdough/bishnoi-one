from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select,func
from app.models import SalesOrder,JournalEntry,Invoice,Notification,RolePermission
from .test_tax_api import app,ana,ben,client  # noqa: F401
from .test_dashboard import person

PERMS=['sales_orders.view','sales_orders.create','sales_orders.submit','sales_orders.approve','sales_orders.cancel']
BODY={'customerName':'Fictional order buyer','orderDate':'2026-10-27','pricesIncludeTax':True,'lines':[{'description':'Sample medicine pack','quantity':1,'unitPriceCentavos':1120000,'category':'standard'}]}
def make(client,who,body=None):
 r=client.post('/finance/sales-orders',headers=who,json=body or BODY);assert r.status_code==201,r.text;return r.json()
def step(client,who,order,action,reason=None):
 return client.post(f"/finance/sales-orders/{order['id']}/{action}",headers=who,json={'version':order['version'],'reason':reason})

def test_permissions_enforced_on_every_route(client,ana):
 viewer=person(client,ana,'Order viewer',['sales_orders.view'])
 none=person(client,ana,'No order permissions',[])
 draft=person(client,ana,'Draft only',['sales_orders.view','sales_orders.create'])
 order=make(client,draft)
 assert client.get('/finance/sales-orders',headers=none).status_code==403
 assert client.get(f"/finance/sales-orders/{order['id']}",headers=none).status_code==403
 assert client.post('/finance/sales-orders',headers=viewer,json=BODY).status_code==403
 assert step(client,draft,order,'submit').status_code==403
 for action in ('approve','return','cancel','submit'):assert step(client,viewer,order,action,'Example reason').status_code==403
 assert client.put(f"/finance/sales-orders/{order['id']}",headers=viewer,json=BODY).status_code==403
 catalogue=client.get('/admin/roles',headers=ana)
 # Authorisation catalogue is also covered via Finance's role tests; no grant is made here.
 assert order['canEdit'] and not order['canSubmit']

def test_approval_history_queues_notifications_and_no_financial_side_effects(client,ana,app):
 maker=person(client,ana,'SO maker',PERMS)
 approver=person(client,ana,'SO approver',['sales_orders.view','sales_orders.approve'])
 order=make(client,maker)
 assert order['totalCentavos']==1120000 and order['taxCentavos']==120000
 sent=step(client,maker,order,'submit');assert sent.status_code==200,sent.text;sent=sent.json()
 assert step(client,maker,sent,'approve').status_code==403
 assert len(client.get('/finance/sales-orders?queue=to_approve',headers=approver).json()['items'])==1
 assert len(client.get('/finance/sales-orders?queue=waiting',headers=maker).json()['items'])==1
 approved=step(client,approver,sent,'approve');assert approved.status_code==200,approved.text;approved=approved.json()
 assert approved['status']=='approved' and approved['zohoStatus'].startswith('Not connected')
 assert [e['kind'] for e in approved['events']]==['created','submitted','approved']
 assert step(client,approver,sent,'approve').status_code==409
 assert client.put(f"/finance/sales-orders/{order['id']}",headers=maker,json=BODY|{'version':approved['version']}).status_code==409
 with app.state.sessions() as db:
  assert db.scalar(select(func.count()).select_from(JournalEntry))==0
  assert db.scalar(select(func.count()).select_from(Invoice))==0
  assert db.scalar(select(func.count()).select_from(Notification).where(Notification.kind=='sales_order.to_approve'))>=1

def test_return_correction_cancel_and_stale_version(client,ana):
 maker=person(client,ana,'SO corrections',PERMS)
 order=make(client,maker)
 sent=step(client,maker,order,'submit').json()
 assert step(client,ana,sent,'return','x').status_code==422
 returned=step(client,ana,sent,'return','Please correct the price').json()
 assert returned['status']=='returned'
 result=client.put(f"/finance/sales-orders/{order['id']}",headers=maker,json=BODY|{'version':returned['version'],'reference':'Corrected PO'})
 assert result.status_code==200,result.text
 updated=result.json()
 assert client.put(f"/finance/sales-orders/{order['id']}",headers=maker,json=BODY|{'version':returned['version']}).status_code==409
 sent=step(client,maker,updated,'submit').json()
 approved=step(client,ana,sent,'approve').json()
 assert step(client,maker,approved,'cancel','').status_code==422
 cancelled=step(client,maker,approved,'cancel','Customer cancelled order').json()
 assert cancelled['status']=='cancelled' and not cancelled['canEdit']

def test_input_totals_and_concurrent_approval(client,ana):
 maker=person(client,ana,'SO concurrency',PERMS)
 assert client.post('/finance/sales-orders',headers=maker,json=BODY|{'lines':[{'quantity':1,'unitPriceCentavos':100}]}).status_code==422
 assert client.post('/finance/sales-orders',headers=maker,json=BODY|{'lines':[BODY['lines'][0]|{'quantity':-1}]}).status_code==422
 assert client.post('/finance/sales-orders',headers=maker,json=BODY|{'customerTin':'bad'}).status_code==422
 order=make(client,maker)
 sent=step(client,maker,order,'submit').json()
 with ThreadPoolExecutor(max_workers=2) as pool:
  codes=list(pool.map(lambda _:step(client,ana,sent,'approve').status_code,range(2)))
 assert sorted(codes)==[200,409]
 history=client.get(f"/finance/sales-orders/{order['id']}",headers=ana).json()['events']
 assert sum(e['kind']=='approved' for e in history)==1
