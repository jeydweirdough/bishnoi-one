import Link from 'next/link';
import {Plus} from 'lucide-react';
import {load,getCompanyMe,enc} from '../platform/lib/api';
import {PageHeader,Sheet,Particulars,SectionTitle} from '../platform/ui/sheet';
import {LinkButton} from '../platform/ui/button';
import {makeFormat} from '../platform/lib/format';
import {SalesOrderEditor,SalesOrderSteps} from '../sales-orders/controls';
import type {SalesOrder,OrderList} from '../sales-orders/types';
const NOTICE='Local Finance approval only. Zoho is not connected; this does not issue invoices, post accounting entries or release stock.';
type Search=Promise<Record<string,string|string[]|undefined>>;
const one=(value:string|string[]|undefined)=>typeof value==='string'?value:'';
const STATUS:Record<string,string>={created:'Draft created',edited:'Draft updated',submitted:'Submitted for approval',approved:'Approved in Finance',returned:'Returned for correction',cancelled:'Cancelled'};
export async function SalesOrdersPage({searchParams}:{searchParams:Search}){
 const search=await searchParams,q=one(search.q),queue=one(search.queue)||'all',me=await getCompanyMe(),fmt=makeFormat(me.org);
 const data=await load<OrderList>(`/finance/sales-orders?q=${enc(q)}&queue=${enc(queue)}`);
 return <><PageHeader title="Sales orders" actions={data.canCreate&&<LinkButton href="/finance/sales-orders/new" icon={<Plus className="size-4"/>}>New sales order</LinkButton>}>{NOTICE}</PageHeader>
 <div className="mb-4 flex flex-wrap gap-2 text-sm">{[['all','All orders'],['to_approve',`Waiting for me (${data.counts.toApprove})`],['waiting',`Waiting on approval (${data.counts.waiting})`],['mine','My orders'],['returned',`Returned (${data.counts.returned})`]].map(([key,label])=><Link key={key} href={`/finance/sales-orders?queue=${key}&q=${enc(q)}`} className={`rounded-[3px] px-3 py-2 ${queue===key?'bg-hema-tint font-semibold text-hema':'text-ink-2 hover:bg-bench'}`}>{label}</Link>)}</div>
 <form className="mb-3 flex gap-2"><input suppressHydrationWarning type="hidden" name="queue" value={queue}/><input suppressHydrationWarning name="q" defaultValue={q} placeholder="Order, customer or reference" aria-label="Find sales orders" className="h-9 rounded-lg border border-rule-strong bg-sheet px-3 text-sm"/><button suppressHydrationWarning className="text-sm text-hema">Search</button></form>
 <Sheet className="overflow-x-auto"><table className="w-full min-w-[45rem] text-sm"><thead><tr className="border-b border-rule text-left text-caps text-ink-3"><th className="p-3">Date</th><th className="p-3">Sales order</th><th className="p-3">Customer</th><th className="p-3">Reference</th><th className="p-3">Status</th><th className="p-3 text-right">Amount</th></tr></thead><tbody className="divide-y divide-rule">{data.items.map(order=><tr key={order.id}><td className="p-3">{fmt.on({dateStyle:"medium"}).format(new Date(order.date+"T12:00:00Z"))}</td><td className="p-3"><Link href={`/finance/sales-orders/${order.id}`} className="font-medium text-hema hover:underline">{order.number}</Link></td><td className="p-3">{order.customerName}</td><td className="p-3">{order.reference||'—'}</td><td className="p-3">{order.statusLabel}</td><td className="p-3 text-right tabular-nums">{fmt.peso(order.totalCentavos)}</td></tr>)}</tbody></table>{!data.items.length&&<p className="p-6 text-sm text-ink-3">No sales orders match this view.</p>}</Sheet></>;
}
export async function NewSalesOrderPage(){
 const me=await getCompanyMe(),data=await load<OrderList>('/finance/sales-orders');
 if(!data.canCreate){const {forbidden}=await import('next/navigation');forbidden();}
 return <><PageHeader title="New sales order" crumbs={[{href:'/finance/sales-orders',label:'Sales orders'}]}>{NOTICE}</PageHeader><SalesOrderEditor order={null} categories={data.categories} org={me.org}/></>;
}
export async function SalesOrderPage({params,searchParams}:{params:Promise<{id:string}>;searchParams:Search}){
 const {id}=await params,query=await searchParams,me=await getCompanyMe(),fmt=makeFormat(me.org),order=await load<SalesOrder>(`/finance/sales-orders/${enc(id)}`);
 if(one(query.edit)==='1'){
  if(!order.canEdit){const {forbidden}=await import('next/navigation');forbidden();}
  const data=await load<OrderList>('/finance/sales-orders');
  return <><PageHeader title={`Edit ${order.number}`} crumbs={[{href:'/finance/sales-orders',label:'Sales orders'},{href:`/finance/sales-orders/${order.id}`,label:order.number}]}>{NOTICE}</PageHeader><SalesOrderEditor order={order} categories={data.categories} org={me.org}/></>;
 }
 return <><PageHeader title={`${order.number} · ${order.customerName}`} crumbs={[{href:'/finance/sales-orders',label:'Sales orders'}]} actions={order.canEdit&&<LinkButton href={`/finance/sales-orders/${order.id}?edit=1`}>Edit draft</LinkButton>}>{NOTICE}</PageHeader>
 <p className="mb-4 text-sm font-semibold">{order.statusLabel} · {order.zohoStatus}</p><Sheet className="space-y-4 p-5"><Particulars items={[["Customer",order.customerName],["TIN",order.customerTin],["Address",order.customerAddress],["Order date",fmt.on({dateStyle:"medium"}).format(new Date(order.date+"T12:00:00Z"))],["Reference / PO",order.reference],["Sales rep",order.salesperson],["Terms",`${order.termsDays} days`],["Prepared by",order.createdBy]]}/><SalesOrderSteps order={order}/></Sheet>
 <Sheet className="mt-5 overflow-x-auto p-5"><SectionTitle>Order lines</SectionTitle><table className="w-full min-w-[40rem] text-sm"><thead><tr className="border-b border-rule text-left"><th className="py-2">Item</th><th>Qty</th><th>Unit price</th><th>Discount</th><th>VAT category</th></tr></thead><tbody>{order.lines.map((line,index)=><tr key={index} className="border-b border-rule"><td className="py-2">{line.description||line.ref}</td><td>{line.quantity}</td><td>{fmt.peso(line.unitPriceCentavos)}</td><td>{fmt.peso(line.discountCentavos)}</td><td>{({'standard':'VATable','zero_rated':'Zero-rated','exempt':'VAT-exempt'} as Record<string,string>)[line.category]||line.category}</td></tr>)}</tbody></table><div className="mt-4 text-right text-sm"><p>Prices {order.pricesIncludeTax?'include':'exclude'} VAT</p><p>VAT: {fmt.peso(order.taxCentavos)}</p><p className="font-semibold">Order total: {fmt.peso(order.totalCentavos)}</p></div>{order.notes&&<p className="mt-4 whitespace-pre-wrap text-sm">{order.notes}</p>}</Sheet>
 <Sheet className="mt-5 p-5"><SectionTitle>History</SectionTitle><ol className="divide-y divide-rule">{order.events.map((event,index)=><li key={index} className="py-2 text-sm"><span className="font-medium">{STATUS[event.kind]||event.kind}</span> · {event.who} · {new Intl.DateTimeFormat(me.org.locale??'en-PH',{dateStyle:'medium',timeStyle:'short',timeZone:me.org.timezone??'Asia/Manila'}).format(new Date(event.at))}{event.reason&&<p className="mt-1 text-ink-2">{event.reason}</p>}</li>)}</ol></Sheet></>;
}
