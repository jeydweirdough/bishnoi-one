"use client";
import {useState,type ReactNode} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {Upload} from 'lucide-react';
import {Button} from '../platform/ui/button';
import {Input,Field,FormError} from '../platform/ui/field';
import {Modal} from '../platform/ui/modal';
import {FigureStrip} from '@/src/platform/ui/list-layout';
import {ExpandableTable} from '@/src/platform/ui/expandable-table';
import {money,readFiles,send,type ImportKind,type ImportPlan,type ImportRow,type Outcome,type SourceFile} from './types';

// Bills, Payment vouchers, Sales invoices and Imported expenses → their import button
// (app/routers/imports.py): preview first, then import exactly what the preview showed (its planKey).
// Testing site only for now.

const OUTCOMES:Record<Outcome,string>={ready:'Ready',held:'Held',skipped:'Skipped',imported:'Already imported'};
const DONE:Record<Outcome,string>={ready:'Imported now',held:'Held',skipped:'Skipped',imported:'Already imported'};

const MATCHING=<Link href="/finance/import-matching" className="underline">Import matching</Link>;
type Setup={button:string;title:string;noun:string;files:number;field:string;hint:string;record:string;party:string;source:string;about:ReactNode;ask:string};
const SETUP:Record<ImportKind,Setup>={
 bills:{button:'Import from Zoho export',title:'Import bills from a Zoho export',noun:'bills',files:2,field:'Two CSV files',hint:'The Zoho Bills export and the Zoho Vendor Payments export, chosen together, up to 16 MB.',record:'Bill',party:'Supplier',source:'Zoho ID',ask:'Choose both files together: the Zoho Bills export and the Vendor Payments export.',
  about:<><p>Import bills first; payments need their bills in Finance.</p><p>Approvals happened in Zoho; imported records are marked as imported and are not re-approved.</p><p>Records already imported are never imported twice. Labels must be matched and confirmed first on {MATCHING}.</p></>},
 'supplier-payments':{button:'Import from Zoho export',title:'Import supplier payments from a Zoho export',noun:'payments',files:2,field:'Two CSV files',hint:'The Zoho Bills export and the Zoho Vendor Payments export, chosen together, up to 16 MB.',record:'Payment',party:'Supplier',source:'Zoho ID',ask:'Choose both files together: the Zoho Bills export and the Vendor Payments export.',
  about:<><p>Import bills first; payments need their bills in Finance.</p><p>Approvals happened in Zoho; imported records are marked as imported and are not re-approved.</p><p>Records already imported are never imported twice. Labels must be matched and confirmed first on {MATCHING}.</p></>},
 'oojeema-sales':{button:'Import Oojeema sales',title:'Import Oojeema sales',noun:'invoices and receipts',files:2,field:'Two CSV files',hint:"Oojeema's Sales Journal and Receipt Journal, chosen together, up to 8 MB.",record:'Invoice or receipt',party:'Customer',source:'Oojeema number',ask:"Choose both files together: Oojeema's Sales Journal and Receipt Journal.",
  about:<><p>One invoice for each SI/BI number, with that number and the amounts Oojeema shows. No number is taken from Finance&apos;s BIR series.</p><p>Each receipt comes in whole, or not at all. A receipt that settles an older invoice waits for opening balances.</p><p>Records already imported are never imported twice. Deposit accounts are matched and confirmed first on {MATCHING}.</p></>},
 expenses:{button:'Import from Zoho export',title:'Import expenses from a Zoho export',noun:'expenses',files:1,field:'One CSV file',hint:'The Zoho Expenses export, up to 8 MB.',record:'Expense',party:'Vendor',source:'Zoho ID',ask:'Choose the Zoho Expenses export.',
  about:<><p>Zoho expense history is read-only: they aren&apos;t petty cash, and they have no receipt files.</p><p>Records already imported are never imported twice. Labels must be matched and confirmed first on {MATCHING}.</p></>},
};

function RowDetail({row,source}:{row:ImportRow;source:string}){
 return <div className="space-y-2 text-sm"><p className="text-meta text-ink-3">{source} {row.sourceId}{row.company?` · ${row.company==='2mg'?'2MG':row.company==='gpi'?'GPI':row.company}`:''}</p>
  {row.reasons.length>0?<ul className="list-disc space-y-1 pl-5">{row.reasons.map(r=><li key={r}>{r}</li>)}</ul>:<p className="text-ink-2">{row.outcome==='ready'?'Nothing holds it back.':'No reasons given.'}</p>}
  {row.billId&&<Link href={`/finance/bills/${row.billId}`} className="underline">Open the bill</Link>}
  {row.voucherId&&<Link href={`/finance/vouchers/${row.voucherId}`} className="underline">Open the payment voucher</Link>}
  {row.invoiceId&&<Link href={`/finance/invoices/${row.invoiceId}`} className="underline">Open the invoice</Link>}
  {row.expenseId&&<Link href={`/finance/petty-cash/imported/${row.expenseId}`} className="underline">Open the imported expense</Link>}</div>;
}

export function ZohoImport({kind}:{kind:ImportKind}){
 const router=useRouter();
 const setup=SETUP[kind];
 const [open,setOpen]=useState(false),[picked,setPicked]=useState<File[]>([]),[files,setFiles]=useState<SourceFile[]>([]),[plan,setPlan]=useState<ImportPlan|null>(null),[done,setDone]=useState<ImportPlan|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState<string|null>(null),[show,setShow]=useState<Outcome|'all'>('all'),[page,setPage]=useState(1),[part,setPart]=useState<'all'|'invoice'|'receipt'>('all');
 function reset(){setPicked([]);setFiles([]);setPlan(null);setDone(null);setError(null);setShow('all');setPage(1);setPart('all');}
 function close(){if(busy)return;setOpen(false);reset();}
 async function preview(){
  setBusy(true);setError(null);setPlan(null);setDone(null);
  try{const contents=picked.length?await readFiles(picked,setup.files,setup.ask):files;if(contents.length!==setup.files)throw new Error(setup.ask);
   const result=await send<ImportPlan>(`/finance/import-matching/run?kind=${kind}&step=preview`,{files:contents});setFiles(contents);setPicked([]);setPlan(result);setShow(result.counts.held?'held':'all');setPage(1);}
  catch(e){setError(e instanceof Error?e.message:'The preview could not finish.');}finally{setBusy(false);}
 }
 async function run(){
  if(!plan)return;
  setBusy(true);setError(null);
  try{const result=await send<ImportPlan>(`/finance/import-matching/run?kind=${kind}&step=import`,{files,planKey:plan.planKey});setDone(result);setPlan(null);setShow('ready');setPage(1);router.refresh();}
  catch(e){setError(e instanceof Error?e.message:'The import could not finish. Nothing was saved.');}finally{setBusy(false);}
 }
 const shown=done??plan;
 const rows=(shown?.rows||[]).filter(r=>(show==='all'||r.outcome===show)&&(part==='all'||r.kind===part));
 const ready=plan?.counts.ready??0;
 const words=done?DONE:OUTCOMES;
 const strip=(counts:Record<Outcome,number>)=>(['ready','held','skipped','imported'] as Outcome[]).map(k=>({label:words[k],value:String(counts[k]??0)}));
 return <><Button icon={<Upload className="size-4" aria-hidden/>} onClick={()=>setOpen(true)}>{setup.button}</Button>
 <Modal open={open} title={setup.title} onCancel={close} footer={null} width={960}>
  <div className="mt-3 space-y-4">
   <div className="space-y-1 text-sm text-ink-2">{setup.about}</div>
   {!done&&<><Field label={setup.field} hint={setup.hint}>{props=><Input {...props} suppressHydrationWarning type="file" accept=".csv,text/csv" multiple={setup.files>1} disabled={busy} onChange={e=>{setPicked(Array.from(e.target.files||[]));setPlan(null);setError(null);}}/>}</Field>
    <div className="flex flex-wrap items-center gap-3"><Button variant={plan?'default':'primary'} loading={busy&&!plan} disabled={busy||(picked.length!==setup.files&&files.length!==setup.files)} onClick={preview}>{plan?'Preview again':'Preview'}</Button><span className="text-meta text-ink-3">{picked.length===setup.files?`${picked.length} ${picked.length===1?'file':'files'} selected`:picked.length?`${picked.length} selected: choose exactly ${setup.files}`:files.length?files.map(f=>f.name).join(' · '):'No files selected'}</span></div></>}
   <FormError message={error}/>
   {shown&&<div className="space-y-4 border-t border-rule pt-4">
    {done&&<p role="status" className="font-semibold">{done.counts.ready} {setup.noun} imported. {done.counts.held} held · {done.counts.skipped} skipped · {done.counts.imported} already imported.</p>}
    {shown.notice&&<p className="rounded-[3px] bg-promo-tint px-4 py-2 text-sm text-ink">{shown.notice}</p>}
    {shown.parts?shown.parts.map(p=><div key={p.label}><p className="mb-1 text-sm font-semibold">{p.label}</p><div className="overflow-hidden rounded-xl border border-rule"><FigureStrip figures={strip(p.counts)}/></div></div>)
     :<div className="overflow-hidden rounded-xl border border-rule"><FigureStrip figures={strip(shown.counts)}/></div>}
    {shown.figures&&<p className="text-sm text-ink-2">Would post: sales {money(shown.figures.amountCentavos)}, of which Output VAT {money(shown.figures.vatCentavos)}. Money received {money(shown.figures.cashCentavos)}, tax withheld {money(shown.figures.cwtCentavos)}.</p>}
    {shown.reasons.length>0&&<div><p className="text-sm font-semibold">Why records are held</p><ul className="mt-1 space-y-1 text-sm">{shown.reasons.map(r=><li key={r.reason} className="flex justify-between gap-3 border-t border-rule py-1"><span>{r.reason}</span><span className="shrink-0 text-ink-3">{r.records} {r.records===1?'record':'records'}</span></li>)}</ul><p className="mt-2 text-meta text-ink-3">Missing matches are fixed on {MATCHING}; then preview again.</p></div>}
    {shown.parts&&<div className="flex flex-wrap gap-2">{([['all','Invoices and receipts'],['invoice','Invoices'],['receipt','Receipts']] as const).map(([k,label])=><Button key={k} size="sm" variant={part===k?'primary':'quiet'} onClick={()=>{setPart(k);setPage(1);}}>{label}</Button>)}</div>}
    <div className="flex flex-wrap gap-2">{(['all','ready','held','skipped','imported'] as const).map(k=><Button key={k} size="sm" variant={show===k?'primary':'quiet'} onClick={()=>{setShow(k);setPage(1);}}>{k==='all'?'All':words[k]} {k==='all'?shown.rows.length:shown.counts[k]??0}</Button>)}</div>
    <div className="rounded-xl border border-rule"><ExpandableTable minWidth="44rem" columns={[{key:'number',label:setup.record},{key:'party',label:setup.party},{key:'date',label:'Date'},{key:'total',label:'Total',align:'right'},{key:'outcome',label:'Outcome'}]} rows={rows.slice((page-1)*20,page*20).map(r=>({id:`${r.kind??''}-${r.sourceId}`,muted:r.outcome==='skipped'||r.outcome==='imported',cells:[
     <span key="number" className="font-medium">{r.number}</span>,<span key="party">{r.party}</span>,<span key="date">{r.date}</span>,<span key="total">{money(r.total)}</span>,
     <span key="outcome">{words[r.outcome]}{r.reasons.length>0&&<span className="block text-meta text-ink-3">{r.reasons.length} {r.reasons.length===1?'reason':'reasons'}</span>}</span>],detail:<RowDetail row={r} source={setup.source}/>}))}/>
     {rows.length===0&&<p className="p-4 text-sm text-ink-3">No records in this view.</p>}</div>
    {rows.length>20&&<div className="flex items-center gap-3 text-sm"><span>{rows.length} records · Page {page}</span><Button size="sm" disabled={page===1} onClick={()=>setPage(page-1)}>Previous</Button><Button size="sm" disabled={page*20>=rows.length} onClick={()=>setPage(page+1)}>Next</Button></div>}
    {plan&&<div className="flex flex-wrap items-center justify-end gap-3 border-t border-rule pt-4">{ready===0&&<span className="text-sm text-ink-2">Nothing is ready to import. Resolve the held reasons, then preview again.</span>}<Button variant="primary" loading={busy} disabled={ready===0} onClick={()=>{if(window.confirm(`Import ${ready} ${setup.noun} into Finance? They are posted to the books as imported records.`))run();}}>Import {ready} {setup.noun}</Button></div>}
    {done&&<div className="flex justify-end gap-2 border-t border-rule pt-4"><Button onClick={reset}>Import more</Button><Button variant="primary" onClick={close}>Close</Button></div>}
   </div>}
  </div>
 </Modal></>;
}
