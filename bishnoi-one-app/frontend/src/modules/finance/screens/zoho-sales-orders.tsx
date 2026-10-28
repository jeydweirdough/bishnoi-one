import Link from 'next/link';
import {load,enc,getCompanyMe} from '../platform/lib/api';
import {PageHeader,Sheet,SectionTitle,Particulars} from '../platform/ui/sheet';
import {ListFrame,FigureStrip,UnderlineTabs,ListToolbar} from '@/src/platform/ui/list-layout';
import {ExpandableTable} from '@/src/platform/ui/expandable-table';
import {Pager} from '@/src/platform/ui/pager';
import {SourceNotice,SourceStatus,SourcePeriod,SourceEmpty,SourceRecordLink} from '../zoho/source-list';
import {LinkButton} from '../platform/ui/button';
import {SourceCoverage,type SourceCoverageData} from '../zoho/source-status';
import {SavedDataRefresh} from '../zoho/saved-refresh';
type Search=Promise<Record<string,string|string[]|undefined>>;
type Invoice={id:string;number:string;date:string;status:string;company:'2mg'|'gpi'|'unknown';invoicingFrom:string;currency:string;totalCentavos:number;balanceCentavos:number|null;lines:Line[]};
type Line={id:string|null;orderLineId:string|null;name:string;quantity:string;unitPriceCentavos:number|null;amountCentavos:number|null};
type Order={id:string;number:string;date:string;status:string;customerName:string;reference:string;salesperson:string;currency:string;totalCentavos:number;lines:Line[];invoices:Invoice[];has2mg:boolean;companyLabel:string;missingInvoiceDetails:number;relationshipIssues:number;twoMgInvoiceTotals:{currency:string;centavos:number}[];fetchedAt:string;detailLoaded?:boolean;declaredInvoicingFrom?:string;invoicedStatus?:string};
type List={items:Order[];total:number;page:number;pageSize:number;savedCount:number;twoMgCount:number;localCount:number;coverage:SourceCoverageData|null};
const one=(v:string|string[]|undefined)=>typeof v==='string'?v:'';
function amount(cents:number|null,currency:string){if(cents===null)return '—';return /^[A-Z]{3}$/.test(currency)?new Intl.NumberFormat('en-PH',{style:'currency',currency}).format(cents/100):`${(cents/100).toFixed(2)} (currency missing)`;}
function on(value:string){return new Intl.DateTimeFormat('en-PH',{dateStyle:'medium'}).format(new Date(value+'T12:00:00Z'));}
function saved(value:string){return new Intl.DateTimeFormat('en-PH',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Manila'}).format(new Date(value.endsWith('Z')||/[+-]\d\d:\d\d$/.test(value)?value:value+'Z'));}
const state=(value:string)=>value.replaceAll('_',' ');

export async function ZohoSalesOrdersPage({searchParams}:{searchParams:Search}){
 const search=await searchParams,me=await getCompanyMe();
 const company=one(search.company)==='all'?'all':'2mg',q=one(search.q),period=['q1','all'].includes(one(search.period))?one(search.period):'month';
 const asked=Number(one(search.page)),requestedPage=Number.isInteger(asked)&&asked>0?asked:1;
 const data=await load<List>(`/finance/zoho-sales-orders?company=${company}&period=${period}&q=${enc(q)}&page=${requestedPage}`);
 const href=(co:string)=>`/finance/sales-orders?company=${co}&period=${period}&q=${enc(q)}`;
 const record=(id:string)=>`/finance/sales-orders/zoho/${enc(id)}?company=${company}&period=${period}&q=${enc(q)}&page=${data.page}`;
 const mayInvoice=me.permissions?.includes('invoices.view');
 return <><SavedDataRefresh/>
  <PageHeader title="Sales orders" actions={<LinkButton href="/finance/sales-orders/local">Finance-created orders</LinkButton>}>Follow each Zoho order through its linked invoices.</PageHeader>
  <SourceNotice/><SourceCoverage coverage={data.coverage}/>
  <div data-source-list><ListFrame>
   <FigureStrip figures={[{label:'Orders saved in period',value:data.savedCount.toLocaleString('en-PH')},{label:'2MG-related orders',value:data.twoMgCount.toLocaleString('en-PH')},{label:'Matching filters',value:data.total.toLocaleString('en-PH')}]}/>
   <UnderlineTabs label="Company focus" tabs={[{href:href('2mg'),label:'2MG-related',count:data.twoMgCount,current:company==='2mg'},{href:href('all'),label:'All companies',count:data.savedCount,current:company==='all'}]}/>
   <ListToolbar q={q} placeholder="Search order, customer or invoice" keep={{company,period}}><SourcePeriod company={company} period={period} q={q}/></ListToolbar>
   {data.items.length?<ExpandableTable minWidth="58rem" columns={[
    {key:'order',label:'Order / date'},{key:'customer',label:'Customer'},{key:'company',label:'Company indication'},
    {key:'invoices',label:'Saved invoice links'},{key:'status',label:'Zoho status'},{key:'amount',label:'Full order total',align:'right'},
   ]} rows={data.items.map(order=>({id:order.id,cells:[
    <div key="order"><SourceRecordLink href={record(order.id)}>{order.number}</SourceRecordLink><p className="mt-1 text-meta text-ink-3">{on(order.date)}</p></div>,
    <span key="customer" className="block max-w-64">{order.customerName}</span>,<span key="company">{order.companyLabel}</span>,
    <div key="invoices"><span>{order.invoices.length} saved</span>{order.missingInvoiceDetails>0&&<p className="text-meta text-ink-3">More links being checked</p>}</div>,
    <SourceStatus key="status" value={order.status}/>,<span key="amount" className="whitespace-nowrap">{amount(order.totalCentavos,order.currency)}</span>,
   ],detail:<div className="grid gap-5 lg:grid-cols-2">
    <div><SectionTitle>Order context</SectionTitle><div className="mt-3"><Particulars items={[["Customer PO / reference",order.reference||null],["Sales rep",order.salesperson||null],["Saved",saved(order.fetchedAt)]]}/></div>
     <p className="mt-3 text-meta text-ink-3">The full order may include GPI and 2MG. Only the invoice's Invoicing From confirms its company.</p>
     <p className="mt-3"><SourceRecordLink href={record(order.id)}>Open full order</SourceRecordLink></p>
    </div>
    <div><SectionTitle>Linked invoices</SectionTitle>{order.invoices.length?<ul className="mt-2 divide-y divide-rule">{order.invoices.map(invoice=><li key={invoice.id} className="flex flex-wrap justify-between gap-2 py-2 text-sm"><div>{mayInvoice?<SourceRecordLink href={`/finance/invoices/zoho/${enc(invoice.id)}`}>{invoice.number}</SourceRecordLink>:invoice.number}<p className="text-meta text-ink-3">{invoice.invoicingFrom||'Company not yet confirmed'}</p></div><span>{amount(invoice.totalCentavos,invoice.currency)}</span></li>)}</ul>:<p className="mt-3 text-sm text-ink-2">No invoice links saved yet. This does not confirm that no invoice exists in Zoho.</p>}
     {(order.detailLoaded===false||order.missingInvoiceDetails>0)&&<p className="mt-2 text-meta text-ink-3">Full details and links are still being checked in the background.</p>}
     {order.relationshipIssues>0&&<p className="mt-2 text-sm text-ink-2">Some saved links need verification. They are excluded from the 2MG invoice figure.</p>}
    </div>
   </div>}))}/>:<SourceEmpty kind="orders" filtered={Boolean(q||company!=='all')} savedCount={data.savedCount} clear={`/finance/sales-orders?company=all&period=${period}`} canManage={me.permissions?.includes('integrations.manage')??false}/>}
   <p className="border-t border-rule px-5 py-3 text-meta text-ink-3">2MG-related includes confirmed invoice links or an indication on the order. Unconfirmed company records remain under All companies.</p>
  </ListFrame></div>
  <Pager total={data.total} page={data.page} size={data.pageSize} base={href(company)} noun="orders"/>
 </>;
}

export async function ZohoSalesOrderPage({params,searchParams}:{params:Promise<{id:string}>;searchParams:Search}){
 const [{id},query]=await Promise.all([params,searchParams]);
 const me=await getCompanyMe();
 const order=await load<Order>(`/finance/zoho-sales-orders/${enc(id)}`),company=one(query.company)==='all'?'all':'2mg';
 const back=`/finance/sales-orders?company=${company}&period=${enc(one(query.period)||'month')}&q=${enc(one(query.q))}&page=${Math.max(1,Number(one(query.page))||1)}`;
 return <><PageHeader title={`${order.number} · ${order.customerName}`} crumbs={[{href:back,label:'Sales orders'}]}>Order details and linked invoices saved from Zoho.</PageHeader><SourceNotice/>
 <p className="mb-4 text-sm">{order.companyLabel} · Zoho: <span className="capitalize">{state(order.status)}</span> · Saved {saved(order.fetchedAt)}</p>
 <Sheet className="space-y-4 p-5"><Particulars items={[["Customer",order.customerName],["Order date",on(order.date)],["Reference",order.reference||null],["Sales rep",order.salesperson||null],["Full SO total",amount(order.totalCentavos,order.currency)],["2MG invoices in saved data",order.twoMgInvoiceTotals.length?order.twoMgInvoiceTotals.map(x=>amount(x.centavos,x.currency)).join(' · '):'None confirmed'] ]}/><p className="text-meta text-ink-3">The full order can cover more than one company. The 2MG figure includes only saved invoices attributed to 2MG; it is not a posted sales or BIR total.</p></Sheet>
 <Sheet className="mt-5 overflow-x-auto p-5"><SectionTitle>Linked invoices</SectionTitle><table className="mt-3 w-full min-w-[45rem] text-sm"><thead><tr className="border-b border-rule text-left"><th className="py-2">Invoice number</th><th>Date</th><th>Invoicing From</th><th>Zoho status</th><th className="text-right">Invoice total</th><th className="text-right">Current balance</th></tr></thead><tbody>{order.invoices.map(invoice=><tr key={invoice.id} className="border-b border-rule"><td className="py-3 font-medium">{me.permissions?.includes('invoices.view')?<Link href={`/finance/invoices/zoho/${enc(invoice.id)}`} className="text-hema hover:underline">{invoice.number}</Link>:invoice.number}</td><td>{on(invoice.date)}</td><td>{invoice.invoicingFrom||'Not yet attributed'}</td><td className="capitalize">{state(invoice.status)}</td><td className="text-right tabular-nums">{amount(invoice.totalCentavos,invoice.currency)}</td><td className="text-right tabular-nums">{amount(invoice.balanceCentavos,invoice.currency)}</td></tr>)}</tbody></table>{!order.invoices.length&&<p className="py-3 text-sm text-ink-3">Invoice links have not been saved yet; company allocation is not assumed.</p>}{order.missingInvoiceDetails>0&&<p className="mt-3 text-sm text-ink-2">{order.missingInvoiceDetails} linked invoice details have not yet been read. This view is incomplete.</p>}{order.relationshipIssues>0&&<p className="mt-3 text-sm text-ink-2">{order.relationshipIssues} invoice links need verification and are excluded from the 2MG figure.</p>}<p className="mt-3 text-meta text-ink-3">Original invoice numbers are preserved. Current balances are from the saved Zoho response; they are not reconstructed quarter-end balances. INV’s official Oojeema lifecycle is still being confirmed.</p></Sheet>
 <Sheet className="mt-5 overflow-x-auto p-5"><SectionTitle>Sales order lines</SectionTitle>{order.detailLoaded===false&&<p className="mt-3 text-sm text-ink-2">Order summary saved. Current line details and invoice links are still downloading in the background.</p>}<table className="mt-3 w-full min-w-[35rem] text-sm"><thead><tr className="border-b border-rule text-left"><th className="py-2">Item</th><th>Quantity</th><th className="text-right">Unit price</th><th className="text-right">Line total</th></tr></thead><tbody>{(order.detailLoaded===false?[]:order.lines).map((line,index)=><tr key={line.id??index} className="border-b border-rule"><td className="py-3">{line.name}</td><td>{line.quantity}</td><td className="text-right tabular-nums">{amount(line.unitPriceCentavos,order.currency)}</td><td className="text-right tabular-nums">{amount(line.amountCentavos,order.currency)}</td></tr>)}</tbody></table></Sheet></>;
}
