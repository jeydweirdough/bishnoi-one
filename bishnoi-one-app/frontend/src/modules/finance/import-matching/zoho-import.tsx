"use client";
import {useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {Upload} from 'lucide-react';
import {Button} from '../platform/ui/button';
import {Input,Field,FormError} from '../platform/ui/field';
import {Modal} from '../platform/ui/modal';
import {FigureStrip} from '@/src/platform/ui/list-layout';
import {ExpandableTable} from '@/src/platform/ui/expandable-table';
import {money,readPair,send,type ImportKind,type ImportPlan,type ImportRow,type Outcome,type SourceFile} from './types';

// Bills and Payment vouchers → Import from Zoho export (app/routers/imports.py): preview first,
// then import exactly what the preview showed (its planKey). Testing site only for now.

const OUTCOMES:Record<Outcome,string>={ready:'Ready',held:'Held',skipped:'Skipped',imported:'Already imported'};
const DONE:Record<Outcome,string>={ready:'Imported now',held:'Held',skipped:'Skipped',imported:'Already imported'};

function RowDetail({row,kind}:{row:ImportRow;kind:ImportKind}){
 return <div className="space-y-2 text-sm"><p className="text-meta text-ink-3">Zoho ID {row.sourceId} · {row.company||'Company not given'}</p>
  {row.reasons.length>0?<ul className="list-disc space-y-1 pl-5">{row.reasons.map(r=><li key={r}>{r}</li>)}</ul>:<p className="text-ink-2">{row.outcome==='ready'?'Nothing holds it back.':'No reasons given.'}</p>}
  {row.billId&&kind==='bills'&&<Link href={`/finance/bills/${row.billId}`} className="underline">Open the bill</Link>}
  {row.voucherId&&<Link href={`/finance/vouchers/${row.voucherId}`} className="underline">Open the payment voucher</Link>}</div>;
}

export function ZohoImport({kind}:{kind:ImportKind}){
 const router=useRouter();
 const noun=kind==='bills'?'bills':'payments';
 const [open,setOpen]=useState(false),[picked,setPicked]=useState<File[]>([]),[files,setFiles]=useState<SourceFile[]>([]),[plan,setPlan]=useState<ImportPlan|null>(null),[done,setDone]=useState<ImportPlan|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState<string|null>(null),[show,setShow]=useState<Outcome|'all'>('all'),[page,setPage]=useState(1);
 function reset(){setPicked([]);setFiles([]);setPlan(null);setDone(null);setError(null);setShow('all');setPage(1);}
 function close(){if(busy)return;setOpen(false);reset();}
 async function preview(){
  setBusy(true);setError(null);setPlan(null);setDone(null);
  try{const contents=picked.length?await readPair(picked):files;if(contents.length!==2)throw new Error('Choose both files together: the Zoho Bills export and the Vendor Payments export.');
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
 const rows=(shown?.rows||[]).filter(r=>show==='all'||r.outcome===show);
 const ready=plan?.counts.ready??0;
 return <><Button icon={<Upload className="size-4" aria-hidden/>} onClick={()=>setOpen(true)}>Import from Zoho export</Button>
 <Modal open={open} title={kind==='bills'?'Import bills from a Zoho export':'Import supplier payments from a Zoho export'} onCancel={close} footer={null} width={960}>
  <div className="mt-3 space-y-4">
   <div className="space-y-1 text-sm text-ink-2"><p>Import bills first; payments need their bills in Finance.</p><p>Approvals happened in Zoho; imported records are marked as imported and are not re-approved.</p><p>Records already imported are never imported twice. Labels must be matched and confirmed first on <Link href="/finance/import-matching" className="underline">Import matching</Link>.</p></div>
   {!done&&<><Field label="Two CSV files" hint="The Zoho Bills export and the Zoho Vendor Payments export, chosen together, up to 16 MB.">{props=><Input {...props} type="file" accept=".csv,text/csv" multiple disabled={busy} onChange={e=>{setPicked(Array.from(e.target.files||[]));setPlan(null);setError(null);}}/>}</Field>
    <div className="flex flex-wrap items-center gap-3"><Button variant={plan?'default':'primary'} loading={busy&&!plan} disabled={busy||(picked.length!==2&&files.length!==2)} onClick={preview}>{plan?'Preview again':'Preview'}</Button><span className="text-meta text-ink-3">{picked.length===2?'2 files selected':picked.length?`${picked.length} selected: choose exactly 2`:files.length?files.map(f=>f.name).join(' · '):'No files selected'}</span></div></>}
   <FormError message={error}/>
   {shown&&<div className="space-y-4 border-t border-rule pt-4">
    {done&&<p role="status" className="font-semibold">{done.counts.ready} {noun} imported. {done.counts.held} held · {done.counts.skipped} skipped · {done.counts.imported} already imported.</p>}
    <div className="overflow-hidden rounded-xl border border-rule"><FigureStrip figures={(['ready','held','skipped','imported'] as Outcome[]).map(k=>({label:(done?DONE:OUTCOMES)[k],value:String(shown.counts[k]??0)}))}/></div>
    {shown.reasons.length>0&&<div><p className="text-sm font-semibold">Why records are held</p><ul className="mt-1 space-y-1 text-sm">{shown.reasons.map(r=><li key={r.reason} className="flex justify-between gap-3 border-t border-rule py-1"><span>{r.reason}</span><span className="shrink-0 text-ink-3">{r.records} {r.records===1?'record':'records'}</span></li>)}</ul><p className="mt-2 text-meta text-ink-3">Missing matches are fixed on <Link href="/finance/import-matching" className="underline">Import matching</Link>; then preview again.</p></div>}
    <div className="flex flex-wrap gap-2">{(['all','ready','held','skipped','imported'] as const).map(k=><Button key={k} size="sm" variant={show===k?'primary':'quiet'} onClick={()=>{setShow(k);setPage(1);}}>{k==='all'?'All':(done?DONE:OUTCOMES)[k]} {k==='all'?shown.rows.length:shown.counts[k]??0}</Button>)}</div>
    <div className="rounded-xl border border-rule"><ExpandableTable minWidth="44rem" columns={[{key:'number',label:kind==='bills'?'Bill':'Payment'},{key:'party',label:'Supplier'},{key:'date',label:'Date'},{key:'total',label:'Total',align:'right'},{key:'outcome',label:'Outcome'}]} rows={rows.slice((page-1)*20,page*20).map(r=>({id:r.sourceId,muted:r.outcome==='skipped'||r.outcome==='imported',cells:[
     <span key="number" className="font-medium">{r.number}</span>,<span key="party">{r.party}</span>,<span key="date">{r.date}</span>,<span key="total">{money(r.total)}</span>,
     <span key="outcome">{(done?DONE:OUTCOMES)[r.outcome]}{r.reasons.length>0&&<span className="block text-meta text-ink-3">{r.reasons.length} {r.reasons.length===1?'reason':'reasons'}</span>}</span>],detail:<RowDetail row={r} kind={kind}/>}))}/>
     {rows.length===0&&<p className="p-4 text-sm text-ink-3">No records in this view.</p>}</div>
    {rows.length>20&&<div className="flex items-center gap-3 text-sm"><span>{rows.length} records · Page {page}</span><Button size="sm" disabled={page===1} onClick={()=>setPage(page-1)}>Previous</Button><Button size="sm" disabled={page*20>=rows.length} onClick={()=>setPage(page+1)}>Next</Button></div>}
    {plan&&<div className="flex flex-wrap items-center justify-end gap-3 border-t border-rule pt-4">{ready===0&&<span className="text-sm text-ink-2">Nothing is ready to import. Resolve the held reasons, then preview again.</span>}<Button variant="primary" loading={busy} disabled={ready===0} onClick={()=>{if(window.confirm(`Import ${ready} ${noun} into Finance? They are posted to the books as imported records.`))run();}}>Import {ready} {noun}</Button></div>}
    {done&&<div className="flex justify-end gap-2 border-t border-rule pt-4"><Button onClick={reset}>Import more</Button><Button variant="primary" onClick={close}>Close</Button></div>}
   </div>}
  </div>
 </Modal></>;
}
