"use client";
import {useEffect,useState} from 'react';
import {ConfigProvider,Select as SearchSelect} from 'antd';
import {Button} from '../platform/ui/button';
import {Input,Select,Field,FormError} from '../platform/ui/field';
import {Modal} from '../platform/ui/modal';
import {confirmRule,loadRules,removeRule,saveRule} from './actions';
import {money,readPair,send,type LabelRecords,type Match,type Matching,type Rule,type RuleIn,type SourceFile} from './types';

// The records behind one label, so Finance sees what they are matching (a bill's lines, a payment).
// Read from the exports loaded on this page; the files aren't stored, so someone else is asked to
// choose them once, only to look. For bill-line accounts and tax labels, a line can also be given its
// own choice, or all lines from its supplier (Sir Mel, 2026-10-29: one Zoho account can stand for
// several of ours, and purchase types vary within one).

type Row=LabelRecords['rows'][number];
const FROM:Record<string,string>={'line choice':'this line','supplier rule':'supplier rule',label:'the label'};

export function RecordsModal({match,choices,files,onFiles,onClose}:{match:Match;choices:Matching['choices'];files:SourceFile[];onFiles:(files:SourceFile[])=>void;onClose:()=>void}){
 const [picked,setPicked]=useState<File[]>([]),[data,setData]=useState<LabelRecords|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState<string|null>(null);
 const [q,setQ]=useState(''),[page,setPage]=useState(1),[rules,setRules]=useState<Rule[]>([]),[editing,setEditing]=useState<string|null>(null);
 const [draft,setDraft]=useState<{accountId?:string|null;purchaseType?:string|null;vatKind?:string|null}>({});
 const lines=match.section==='account'||match.section==='tax';
 const contents=files.length===2?files:null;
 async function look(sourceFiles:SourceFile[]){
  setBusy(true);setError(null);
  try{setData(await send<LabelRecords>(`/finance/import-matching/records?id=${match.id}`,{files:sourceFiles}));}
  catch(e){setError(e instanceof Error?e.message:'The records could not be shown.');}finally{setBusy(false);}
 }
 async function refreshRules(){if(!lines)return;const r=await loadRules(match.id);if(r.ok)setRules(r.data.rules);else setError(r.error);}
 // eslint-disable-next-line react-hooks/exhaustive-deps
 useEffect(()=>{if(contents)look(contents);refreshRules();},[]);
 async function choose(){
  try{const read=await readPair(picked);onFiles(read);await look(read);}catch(e){setError(e instanceof Error?e.message:'Choose the two files again.');}
 }
 async function save(row:Row,scope:'supplier'|'line'){
  const body:RuleIn={scope,supplier:row.party,...(match.section==='account'?{accountId:draft.accountId??null,purchaseType:draft.purchaseType??null}:{vatKind:draft.vatKind??null})};
  if(scope==='line')Object.assign(body,{billSourceId:row.billSourceId,billNumber:row.number,linePosition:row.linePosition,lineAmountCentavos:row.amount});
  setBusy(true);setError(null);
  const r=await saveRule(match.id,body);
  setBusy(false);
  if(!r.ok){setError(r.error);return;}
  setEditing(null);setDraft({});await refreshRules();
  if(data&&(contents||files.length===2))await look(contents??files);
 }
 async function act(fn:()=>Promise<{ok:boolean;error?:string}>){
  setBusy(true);setError(null);const r=await fn();setBusy(false);
  if(!r.ok){setError(r.error??'That could not be saved.');return;}
  await refreshRules();if(data&&contents)await look(contents);
 }
 const rows=(data?.rows||[]).filter(r=>`${r.number} ${r.party} ${r.description} ${r.account} ${r.tax} ${r.accountName??''}`.toLowerCase().includes(q.toLowerCase()));
 const label=match.sourceLabel||'Blank (no label in Zoho)';
 const typeLabel=(k?:string|null)=>choices.purchaseTypes.find(c=>c.key===k)?.label;
 const vatLabel=(k?:string|null)=>choices.vatKinds.find(c=>c.key===k)?.label;
 const takes=(r:Row)=>match.section==='account'
  ?<>{r.accountName??<span className="text-due-today">No account yet</span>}{r.accountId&&r.accountIdFrom&&<span className="block text-meta text-ink-3">from {FROM[r.accountIdFrom]}</span>}<span className="block">{typeLabel(r.purchaseType)??<span className="text-due-today">No purchase type yet</span>}{r.purchaseType&&r.purchaseTypeFrom&&<span className="text-meta text-ink-3"> · from {FROM[r.purchaseTypeFrom]}</span>}</span></>
  :<>{vatLabel(r.vatKind)??<span className="text-due-today">No VAT kind yet</span>}{r.vatKind&&r.vatKindFrom&&<span className="block text-meta text-ink-3">from {FROM[r.vatKindFrom]}</span>}</>;
 const ready=match.section==='account'?Boolean(draft.accountId||draft.purchaseType):Boolean(draft.vatKind);
 const editor=(r:Row)=><div className="space-y-2 rounded-lg bg-sheet p-3">
  {match.section==='account'?<div className="grid gap-2 sm:grid-cols-2">
   <SearchSelect className="w-full" aria-label="Finance account for this choice" showSearch={{optionFilterProp:'label'}} allowClear placeholder="Account (leave empty to keep the label's)" value={draft.accountId||undefined} options={choices.lineAccounts.map(a=>({value:a.id,label:`${a.code} · ${a.name}`}))} onChange={(value:string|undefined)=>setDraft(d=>({...d,accountId:value??null}))}/>
   <Select aria-label="Purchase type for this choice" value={draft.purchaseType??''} onChange={e=>setDraft(d=>({...d,purchaseType:e.target.value||null}))}><option value="">Purchase type (leave empty to keep the label&apos;s)</option>{choices.purchaseTypes.map(c=><option key={c.key} value={c.key}>{c.label}</option>)}</Select></div>
  :<Select aria-label="VAT kind for this choice" value={draft.vatKind??''} onChange={e=>setDraft(d=>({...d,vatKind:e.target.value||null}))}><option value="">Choose VAT kind</option>{choices.vatKinds.map(c=><option key={c.key} value={c.key}>{c.label}</option>)}</Select>}
  <div className="flex flex-wrap gap-2"><Button size="sm" variant="primary" loading={busy} disabled={!ready} onClick={()=>save(r,'line')}>For this line only</Button><Button size="sm" disabled={busy||!ready} onClick={()=>save(r,'supplier')}>For all lines from {r.party}</Button><Button size="sm" variant="quiet" onClick={()=>{setEditing(null);setDraft({});}}>Cancel</Button></div>
  <p className="text-meta text-ink-3">{match.savesConfirmed?'Your save is final.':'Your choice waits for someone who may confirm it.'} A line choice comes first, then the supplier rule, then the label.</p></div>;
 // The window is the browser's own <dialog>, drawn above the page: dropdown lists drawn on the page
 // (antd's default) were hidden behind it, so typing picked the first match unseen. Drawn inside it.
 const inside=(node?:HTMLElement)=>node?.closest('dialog')??document.body;
 return <Modal open title={`Records using “${label}”`} onCancel={onClose} footer={null} width={1040}>
  <ConfigProvider getPopupContainer={inside}>
  <div className="mt-3 space-y-4">
   {!data&&!contents&&<div className="space-y-3"><p className="text-sm text-ink-2">The exports aren&apos;t stored in Finance. Choose the same two files (the Zoho Bills and Vendor Payments exports) to see these records. Nothing is saved.</p>
    <Field label="Two CSV files">{props=><Input {...props} type="file" accept=".csv,text/csv" multiple disabled={busy} onChange={e=>{setPicked(Array.from(e.target.files||[]));setError(null);}}/>}</Field>
    <Button variant="primary" loading={busy} disabled={picked.length!==2} onClick={choose}>Show the records</Button></div>}
   {busy&&!data&&contents&&<p className="text-sm text-ink-2">Reading the exports…</p>}
   <FormError message={error}/>
   {lines&&rules.length>0&&<div className="space-y-1"><p className="text-sm font-semibold">Supplier rules and line choices</p>
    <ul className="text-sm">{rules.map(r=><li key={r.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-rule py-1.5">
     <span>{r.scope==='supplier'?`All lines from ${r.supplier}`:`${r.billNumber} line ${r.linePosition} (${money(r.lineAmountCentavos??0)}), ${r.supplier}`}: {[r.account&&`${r.account.code} · ${r.account.name}`,typeLabel(r.purchaseType),vatLabel(r.vatKind)].filter(Boolean).join(' · ')}
      <span className="block text-meta text-ink-3">{r.status==='confirmed'?(r.confirmedBy===r.proposedBy?`Saved by ${r.confirmedBy}`:`Confirmed by ${r.confirmedBy} (proposed by ${r.proposedBy})`):`Proposed by ${r.proposedBy}: waiting for confirmation`}</span></span>
     <span className="flex gap-2">{r.canConfirm&&<Button size="sm" variant="primary" disabled={busy} onClick={()=>act(()=>confirmRule(r.id))}>Confirm</Button>}{r.canRemove&&<Button size="sm" variant="quiet" disabled={busy} onClick={()=>{if(window.confirm('Remove this choice? Those lines go back to the supplier rule or the label (or are held).'))act(()=>removeRule(r.id));}}>Remove</Button>}</span></li>)}</ul></div>}
   {data&&<>
    <p className="text-sm">{data.total} {data.total===1?'record':'records'} · {money(data.amountCentavos)}{data.shown<data.total?` · the first ${data.shown} are listed`:''}. {lines?'Each row is one bill line that uses this label.':match.section==='money'?'Each row is one supplier payment made through this account.':'Each row is one bill with this company label.'}{data.perRecord?' This label depends on the record: each line needs a supplier rule or its own choice.':''}</p>
    <Input aria-label="Find a bill, supplier or description" placeholder="Find a bill, supplier or description…" value={q} onChange={e=>{setQ(e.target.value);setPage(1);}}/>
    <div className="overflow-x-auto rounded-xl border border-rule"><table className="w-full min-w-[52rem] text-left text-sm"><thead><tr className="text-meta text-ink-3"><th className="px-3 py-2 font-semibold">{match.section==='money'?'Payment':'Bill'}</th><th className="font-semibold">Date</th><th className="font-semibold">Supplier</th><th className="font-semibold">{lines?'Line':'Details'}</th>{lines&&<th className="font-semibold">{match.section==='account'?'Tax label':'Zoho account'}</th>}<th className="text-right font-semibold">Amount</th>{lines&&<th className="px-3 font-semibold">Takes now</th>}{lines&&match.canPropose&&<th/>}</tr></thead>
     <tbody>{rows.slice((page-1)*20,page*20).map((r,i)=>{const id=`${r.billSourceId??r.number}-${r.linePosition??i}`;return [
      <tr key={id} className="border-t border-rule align-top"><td className="px-3 py-2 font-medium">{r.number}</td><td>{r.date}</td><td>{r.party}</td><td>{r.description||<span className="text-ink-3">No description</span>}{r.changed&&<span className="block text-meta text-due-today">Its saved line choice was for a different amount: choose again.</span>}</td>{lines&&<td>{match.section==='account'?r.tax:r.account}</td>}<td className="text-right">{money(r.amount)}</td>
       {lines&&<td className="px-3">{takes(r)}</td>}
       {lines&&match.canPropose&&<td className="pr-3 text-right"><Button size="sm" variant="quiet" onClick={()=>{setEditing(editing===id?null:id);setDraft({});}}>{editing===id?'Close':'Choose'}</Button></td>}</tr>,
      editing===id?<tr key={`${id}-edit`}><td colSpan={match.canPropose?8:7} className="px-3 pb-3">{editor(r)}</td></tr>:null];})}</tbody></table>
     {rows.length===0&&<p className="p-4 text-sm text-ink-3">No records in this view.</p>}</div>
    {rows.length>20&&<div className="flex items-center gap-3 text-sm"><span>{rows.length} records · Page {page}</span><Button size="sm" disabled={page===1} onClick={()=>setPage(page-1)}>Previous</Button><Button size="sm" disabled={page*20>=rows.length} onClick={()=>setPage(page+1)}>Next</Button></div>}
   </>}
   <div className="flex justify-end border-t border-rule pt-4"><Button variant="primary" onClick={onClose}>Close</Button></div>
  </div>
  </ConfigProvider>
 </Modal>;
}
