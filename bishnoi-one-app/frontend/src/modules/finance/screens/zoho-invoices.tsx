import Link from 'next/link';
import {load,enc,getCompanyMe} from '../platform/lib/api';
import {PageHeader,Sheet,SectionTitle,Particulars} from '../platform/ui/sheet';
import {ListFrame,FigureStrip,UnderlineTabs,ListToolbar} from '@/src/platform/ui/list-layout';
import {ExpandableTable} from '@/src/platform/ui/expandable-table';
import {Pager} from '@/src/platform/ui/pager';
import {SourceNotice,SourceStatus,SourcePeriod,SourceEmpty,SourceRecordLink} from '../zoho/source-list';
import {LinkButton} from '../platform/ui/button';
import {SourceCoverage,sourceAmount as amount,sourceDate as on,sourceSaved as saved,type SourceCoverageData} from '../zoho/source-status';
import {SavedDataRefresh} from '../zoho/saved-refresh';
type Search=Promise<Record<string,string|string[]|undefined>>;
type Line={id:string|null;name:string;quantity:string;unitPriceCentavos:number|null;amountCentavos:number|null};
type Invoice={id:string;number:string;date:string;dueDate?:string;status:string;customerName:string;reference:string;company:string;invoicingFrom:string;currency:string;totalCentavos:number;balanceCentavos:number|null;subtotalCentavos?:number|null;taxCentavos?:number|null;withheldCentavos?:number|null;detailLoaded?:boolean;fetchedAt:string;lines:Line[];orders?:{id:string;number:string}[]};
type Listing={items:Invoice[];total:number;page:number;pageSize:number;savedCount:number;twoMgCount:number;localCount:number;coverage:SourceCoverageData|null};
const one=(v:string|string[]|undefined)=>typeof v==='string'?v:'';
const state=(value:string)=>value.replaceAll('_',' ');

export async function ZohoInvoicesPage({searchParams}:{searchParams:Search}){
 const query=await searchParams,me=await getCompanyMe();
 const company=one(query.company)==='all'?'all':'2mg',period=['q1','all'].includes(one(query.period))?one(query.period):'month',q=one(query.q);
 const asked=Number(one(query.page)),page=Number.isInteger(asked)&&asked>0?asked:1;
 const data=await load<Listing>(`/finance/zoho-invoices?company=${company}&period=${period}&q=${enc(q)}&page=${page}`);
 const href=(co:string)=>`/finance/invoices/zoho?company=${co}&period=${period}&q=${enc(q)}`;
 const record=(id:string)=>`/finance/invoices/zoho/${enc(id)}?company=${company}&period=${period}&q=${enc(q)}&page=${data.page}`;
 return <><SavedDataRefresh/>
  <PageHeader title="Zoho invoices" actions={<LinkButton href="/finance/invoices">Finance accounting invoices</LinkButton>}>Review invoice details, company attribution and balances saved from Zoho.</PageHeader>
  <SourceNotice/><SourceCoverage coverage={data.coverage}/>
  <div data-source-list><ListFrame>
   <FigureStrip figures={[{label:'Invoices saved in period',value:data.savedCount.toLocaleString('en-PH')},{label:'2MG invoices',value:data.twoMgCount.toLocaleString('en-PH')},{label:'Matching filters',value:data.total.toLocaleString('en-PH')}]}/>
   <UnderlineTabs label="Invoice company" tabs={[{href:href('2mg'),label:'2MG',count:data.twoMgCount,current:company==='2mg'},{href:href('all'),label:'All companies',count:data.savedCount,current:company==='all'}]}/>
   <ListToolbar q={q} placeholder="Search invoice, customer or reference" keep={{company,period}}><SourcePeriod company={company} period={period} q={q}/></ListToolbar>
   {data.items.length?<ExpandableTable minWidth="58rem" columns={[
    {key:'invoice',label:'Invoice / date'},{key:'customer',label:'Customer'},{key:'company',label:'Invoicing From'},
    {key:'status',label:'Zoho status'},{key:'total',label:'Invoice total',align:'right'},{key:'balance',label:'Saved balance',align:'right'},
   ]} rows={data.items.map(invoice=>({id:invoice.id,cells:[
    <div key="invoice"><SourceRecordLink href={record(invoice.id)}>{invoice.number}</SourceRecordLink><p className="mt-1 text-meta text-ink-3">{on(invoice.date)}</p></div>,
    <span key="customer" className="block max-w-64">{invoice.customerName}</span>,<span key="company">{invoice.invoicingFrom||'Not yet attributed'}</span>,
    <SourceStatus key="status" value={invoice.status}/>,<span key="total" className="whitespace-nowrap">{amount(invoice.totalCentavos,invoice.currency)}</span>,
    <span key="balance" className="whitespace-nowrap">{amount(invoice.balanceCentavos,invoice.currency)}</span>,
   ],detail:<div className="grid gap-5 lg:grid-cols-2">
    <div><SectionTitle>Invoice context</SectionTitle><div className="mt-3"><Particulars items={[["Customer",invoice.customerName],["Due date",invoice.dueDate?on(invoice.dueDate):'Not saved yet'],["Reference",invoice.reference||null],["Saved",saved(invoice.fetchedAt)]]}/></div></div>
    <div><SectionTitle>Reading this balance</SectionTitle><p className="mt-3 text-sm text-ink-2">This is the remaining amount in the saved Zoho record. It is not a reconstructed balance as of quarter-end.</p>
     {invoice.detailLoaded===false&&<p className="mt-2 text-meta text-ink-3">The summary is available. Full lines and order links are still downloading.</p>}
     <p className="mt-3"><SourceRecordLink href={record(invoice.id)}>Open full invoice</SourceRecordLink></p>
    </div>
   </div>}))}/>:<SourceEmpty kind="invoices" filtered={Boolean(q||company!=='all')} savedCount={data.savedCount} clear={`/finance/invoices/zoho?company=all&period=${period}`} canManage={me.permissions?.includes('integrations.manage')??false}/>}
   <p className="border-t border-rule px-5 py-3 text-meta text-ink-3">Company comes from Invoicing From, not INV/GPI/2MG numbering. Original invoice numbers are preserved.</p>
  </ListFrame></div>
  <Pager total={data.total} page={data.page} size={data.pageSize} base={href(company)} noun="invoices"/>
 </>;
}

export async function ZohoInvoicePage({params,searchParams}:{params:Promise<{id:string}>;searchParams:Search}){
 const [{id},q]=await Promise.all([params,searchParams]);const me=await getCompanyMe();const invoice=await load<Invoice>(`/finance/zoho-invoices/${enc(id)}`);
 const back=`/finance/invoices/zoho?company=${one(q.company)==='all'?'all':'2mg'}&period=${enc(one(q.period)||'month')}&q=${enc(one(q.q))}&page=${Math.max(1,Number(one(q.page))||1)}`;
 return <><PageHeader title={`${invoice.number} · ${invoice.customerName}`} crumbs={[{href:back,label:'Zoho invoices'}]}>Invoice details saved from Zoho.</PageHeader><SourceNotice/><p className="mb-4 text-sm">Zoho: <span className="capitalize">{state(invoice.status)}</span> · Saved {saved(invoice.fetchedAt)}</p>
 <Sheet className="space-y-4 p-5"><Particulars items={[["Customer",invoice.customerName],["Invoice date",on(invoice.date)],["Due date",invoice.dueDate?on(invoice.dueDate):null],["Invoicing From",invoice.invoicingFrom||'Not yet attributed'],["Reference",invoice.reference||null],["Invoice total",amount(invoice.totalCentavos,invoice.currency)],["Current source balance",amount(invoice.balanceCentavos,invoice.currency)]]}/>{invoice.orders&&invoice.orders.length>0&&<p className="text-sm">Sales orders: {invoice.orders.map((order,index)=><span key={order.id}>{index>0?' · ':''}{me.permissions?.includes('sales_orders.view')?<Link href={`/finance/sales-orders/zoho/${enc(order.id)}`} className="text-hema hover:underline">{order.number}</Link>:order.number}</span>)}</p>}<p className="text-meta text-ink-3">Original number preserved. INV’s official Oojeema lifecycle is still being confirmed; source balances are not quarter-end reconstructions.</p></Sheet>
 <Sheet className="mt-5 overflow-x-auto p-5"><SectionTitle>Invoice lines</SectionTitle>{invoice.detailLoaded===false?<p className="mt-3 text-sm text-ink-2">The invoice summary is saved. Full line details and order links are still downloading in the background.</p>:<><table className="mt-3 w-full min-w-[35rem] text-sm"><thead><tr className="border-b border-rule text-left"><th className="py-2">Item</th><th>Quantity</th><th className="text-right">Unit price</th><th className="text-right">Line total</th></tr></thead><tbody>{invoice.lines.map((line,index)=><tr key={line.id??index} className="border-b border-rule"><td className="py-3">{line.name}</td><td>{line.quantity}</td><td className="text-right tabular-nums">{amount(line.unitPriceCentavos,invoice.currency)}</td><td className="text-right tabular-nums">{amount(line.amountCentavos,invoice.currency)}</td></tr>)}</tbody></table><div className="mt-4 space-y-1 text-right text-sm"><p>Subtotal: {amount(invoice.subtotalCentavos,invoice.currency)}</p><p>Tax: {amount(invoice.taxCentavos,invoice.currency)}</p><p>Withheld in source record: {amount(invoice.withheldCentavos,invoice.currency)}</p><p className="font-semibold">Total: {amount(invoice.totalCentavos,invoice.currency)}</p></div></>}</Sheet></>;
}
