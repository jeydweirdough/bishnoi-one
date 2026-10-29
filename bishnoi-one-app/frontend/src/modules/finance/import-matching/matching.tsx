"use client";
import {useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {Select as SearchSelect} from 'antd';
import {Button} from '../platform/ui/button';
import {Input,Select,Field,FormError} from '../platform/ui/field';
import {Sheet,SectionTitle} from '../platform/ui/sheet';
import {ListFrame,FigureStrip} from '@/src/platform/ui/list-layout';
import {ExpandableTable} from '@/src/platform/ui/expandable-table';
import {confirmMatch,proposeMatch} from './actions';
import {day,money,readPair,send,type Match,type Matching,type Proposal,type Section} from './types';

// Settings → Import matching (app/routers/imports.py): each label in the Zoho Bills and Vendor
// Payments exports is matched once. Whoever may confirm a section saves it in one step; others
// propose and it waits for them (tax labels: BIR and Compliance). Imports use confirmed matches only.

const SECTIONS:{key:Section;title:string;says:string;choice:string}[]=[
 {key:'company',title:'Company labels',says:'The company each label in the exports stands for.',choice:'Company'},
 {key:'account',title:'Accounts on bill lines',says:'The Finance account and purchase type for each account used on Zoho bill lines.',choice:'Finance account and purchase type'},
 {key:'tax',title:'Tax labels',says:'The VAT kind each Zoho tax label means. BIR and Compliance confirms these.',choice:'VAT kind'},
 {key:'money',title:'Paid-from accounts',says:'The Finance account each Zoho "paid through" account stands for.',choice:'Finance account'},
];
const KINDS:Record<string,string>={bills:'Bills',supplier_payments:'Supplier payments'};
const COUNT_WORDS:Record<string,string>={ready:'imported',held:'held',skipped:'skipped',imported:'already imported'};

/** What the row shows chosen: the person's unsaved choice, else what is saved. */
const chosenOf=(m:Match,draft?:Proposal):Proposal=>({accountId:m.accountId,purchaseType:m.purchaseType,vatKind:m.vatKind,company:m.company,note:'',...draft});
function complete(section:Section,p:Proposal){
 if(section==='company')return Boolean(p.company);
 if(section==='account')return Boolean(p.accountId&&p.purchaseType);
 if(section==='tax')return Boolean(p.vatKind);
 return Boolean(p.accountId);
}
function status(m:Match){
 if(m.status==='open')return m.note?`Not chosen yet. ${m.note}`:'Not chosen yet';
 if(m.status==='proposed')return `Proposed by ${m.proposedBy||'someone'} on ${day(m.proposedAt)}${m.waitingOn?` · waiting for ${m.waitingOn}`:''}`;
 if(m.automatic)return `Filled in automatically on ${day(m.confirmedAt)}. ${m.note??''}`;
 if(m.confirmedBy===m.proposedBy)return `Saved by ${m.confirmedBy||'someone'} on ${day(m.confirmedAt)}`;
 return `Confirmed by ${m.confirmedBy||'someone'} on ${day(m.confirmedAt)} (proposed by ${m.proposedBy||'someone'})`;
}

function MatchSection({section,data}:{section:(typeof SECTIONS)[number];data:Matching}){
 const [drafts,setDrafts]=useState<Record<string,Proposal>>({}),[busy,setBusy]=useState<string|null>(null),[error,setError]=useState<string|null>(null);
 const rows=data.matches.filter(m=>m.section===section.key),counts=data.counts[section.key]??{open:0,proposed:0,confirmed:0};
 const {lineAccounts,moneyAccounts,purchaseTypes,vatKinds,companies}=data.choices;
 const edit=(m:Match,change:Proposal)=>setDrafts(d=>({...d,[m.id]:{...d[m.id],...change}}));
 const dirty=(m:Match)=>{const d=drafts[m.id];return Boolean(d&&((d.accountId!==undefined&&d.accountId!==m.accountId)||(d.purchaseType!==undefined&&d.purchaseType!==m.purchaseType)||(d.vatKind!==undefined&&d.vatKind!==m.vatKind)||(d.company!==undefined&&d.company!==m.company)||d.note));};
 async function propose(m:Match){
  if(m.status==='confirmed'&&!m.savesConfirmed&&!window.confirm('Changing a confirmed match sends it back for confirmation. Imports stop using it until someone who may confirm it does. Continue?'))return;
  const p=chosenOf(m,drafts[m.id]);
  const body:Proposal=section.key==='company'?{company:p.company}:section.key==='account'?{accountId:p.accountId,purchaseType:p.purchaseType}:section.key==='tax'?{vatKind:p.vatKind}:{accountId:p.accountId};
  if(p.note?.trim())body.note=p.note.trim();
  setBusy(m.id);setError(null);
  const result=await proposeMatch(m.id,body);
  setBusy(null);
  if(!result.ok){setError(result.error);return;}
  setDrafts(d=>{const next={...d};delete next[m.id];return next;});
 }
 async function confirm(m:Match){
  setBusy(m.id);setError(null);
  const result=await confirmMatch(m.id);
  setBusy(null);
  if(!result.ok)setError(result.error);
 }
 function choice(m:Match){
  const p=chosenOf(m,drafts[m.id]),off=!m.canPropose||busy===m.id,label=m.sourceLabel||'blank label';
  if(section.key==='company')return <Select aria-label={`Company for ${label}`} disabled={off} placeholder="Choose company" value={p.company??''} onChange={e=>edit(m,{company:e.target.value||null})}>{companies.map(c=><option key={c.key} value={c.key}>{c.label}</option>)}</Select>;
  if(section.key==='tax')return <Select aria-label={`VAT kind for ${label}`} disabled={off} placeholder="Choose VAT kind" value={p.vatKind??''} onChange={e=>edit(m,{vatKind:e.target.value||null})}>{vatKinds.map(c=><option key={c.key} value={c.key}>{c.label}</option>)}</Select>;
  const accounts=section.key==='account'?lineAccounts:moneyAccounts;
  const picker=<SearchSelect className="w-full" aria-label={`Finance account for ${label}`} showSearch={{optionFilterProp:'label'}} allowClear disabled={off} placeholder="Choose the Finance account…" value={p.accountId||undefined} options={accounts.map(a=>({value:a.id,label:`${a.code} · ${a.name}`}))} onChange={(value:string|undefined)=>edit(m,{accountId:value??null})}/>;
  if(section.key==='money')return picker;
  return <div className="space-y-2">{picker}<Select aria-label={`Purchase type for ${label}`} disabled={off} placeholder="Choose purchase type" value={p.purchaseType??''} onChange={e=>edit(m,{purchaseType:e.target.value||null})}>{purchaseTypes.map(c=><option key={c.key} value={c.key}>{c.label}</option>)}</Select></div>;
 }
 return <ListFrame><div className="space-y-1 px-5 pt-4 pb-3"><SectionTitle>{section.title}</SectionTitle><p className="text-sm text-ink-2">{section.says}</p></div>
 <FigureStrip figures={[{label:'Open',value:String(counts.open)},{label:'Waiting for confirmation',value:String(counts.proposed)},{label:'Confirmed',value:String(counts.confirmed)}]}/>
 {error&&<div className="px-5 pt-3"><FormError message={error}/></div>}
 {rows.length===0?<p className="p-5 text-sm text-ink-3">No labels here yet.{data.may.propose?' Load the Zoho exports above.':''}</p>:
 <ExpandableTable minWidth="56rem" columns={[{key:'label',label:'Zoho label'},{key:'records',label:'Records',align:'right'},{key:'amount',label:'Amount',align:'right'},{key:'choice',label:section.choice,className:'w-72'},{key:'status',label:'Status'}]} rows={rows.map(m=>{
  const p=chosenOf(m,drafts[m.id]),changed=dirty(m);
  return {id:m.id,cells:[
   <span key="label" className="font-medium">{m.sourceLabel||<span className="text-ink-3">Blank (no label in Zoho)</span>}{m.sourceCode&&<span className="block text-meta font-normal text-ink-3">{m.sourceCode}</span>}</span>,
   <span key="records">{m.records}</span>,
   <span key="amount">{money(m.amountCentavos)}</span>,
   <div key="choice">{choice(m)}</div>,
   <span key="status" className="text-meta text-ink-2">{status(m)}{m.note&&<span className="block text-ink-3">Note: {m.note}</span>}{changed&&<span className="block text-due-today">Changed here, not proposed yet</span>}</span>,
  ],actions:<>{m.canPropose&&<Button size="sm" variant={m.status==='open'||changed?'primary':'default'} loading={busy===m.id} disabled={!complete(section.key,p)||(m.status!=='open'&&!changed)} title={m.savesConfirmed?'Your save is final; who and when are kept':m.status==='confirmed'?'Changing sends it back for confirmation':'Someone who may confirm it checks it next'} onClick={()=>propose(m)}>{m.status==='confirmed'?'Change':m.savesConfirmed?'Save':'Propose'}</Button>}{m.canConfirm&&<Button size="sm" variant="primary" disabled={busy===m.id||changed} title={changed?'Propose or undo your change first':undefined} onClick={()=>confirm(m)}>Confirm</Button>}</>,
  detail:<div className="grid gap-3 sm:grid-cols-2"><p className="text-sm">{status(m)}{m.mine&&m.status==='proposed'?'. Your proposal: someone else confirms it.':''}</p>{m.canPropose?<Field label="Note with your proposal" optional>{props=><Input {...props} maxLength={300} value={p.note??''} placeholder="Why this choice (optional)" onChange={e=>edit(m,{note:e.target.value})}/>}</Field>:<p className="text-meta text-ink-3">Only people who can propose matches change these.</p>}</div>};
 })}/>}
 </ListFrame>;
}

export function ImportMatching({data}:{data:Matching}){
 const router=useRouter();
 const [picked,setPicked]=useState<File[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState<string|null>(null),[loaded,setLoaded]=useState<{labels:number;new:number}|null>(null);
 async function load(){
  setBusy(true);setError(null);setLoaded(null);
  try{const files=await readPair(picked);setLoaded(await send<{labels:number;new:number}>('/finance/import-matching/load',{files}));setPicked([]);router.refresh();}
  catch(e){setError(e instanceof Error?e.message:'The exports could not be loaded.');}finally{setBusy(false);}
 }
 return <div className="space-y-5"><Sheet className="space-y-3 p-5">
  <p className="text-sm">Match each label from the Zoho exports once. What the export already says is filled in; same-name accounts are suggested. If you may confirm a section, your save is final; otherwise it waits for someone who may. Only confirmed matches are used by imports.</p>
  <p className="text-sm text-ink-2">Imported bills post Accounts payable, Input VAT and tax withheld to Finance&apos;s default accounts, like any bill entered here (<Link href="/finance/ledger/posting" className="underline">Accounting → Default accounts</Link>).</p>
  {!data.importsHere&&<p className="text-sm text-due-today">Imports run on the testing site for now; matching can still be prepared here.</p>}
 </Sheet>
 {data.may.propose&&<Sheet className="space-y-4 p-5"><SectionTitle>Load the Zoho exports</SectionTitle><p className="text-sm text-ink-2">Choose both CSV files together: the Bills export and the Vendor Payments export. Labels already here keep their matches. Nothing is imported.</p>
  <Field label="Two CSV files" hint="The Zoho Bills export and the Zoho Vendor Payments export, up to 16 MB together.">{props=><Input {...props} type="file" accept=".csv,text/csv" multiple disabled={busy} onChange={e=>{setPicked(Array.from(e.target.files||[]));setError(null);setLoaded(null);}}/>}</Field>
  <FormError message={error}/>
  <div className="flex flex-wrap items-center gap-3"><Button variant="primary" loading={busy} disabled={picked.length!==2} onClick={load}>Load the Zoho exports</Button><span className="text-meta text-ink-3">{picked.length===2?'2 files selected':picked.length?`${picked.length} selected: choose exactly 2`:'No files selected'}</span></div>
  {loaded&&<p role="status" className="text-sm font-medium">{loaded.labels} labels, {loaded.new} new.</p>}
 </Sheet>}
 {SECTIONS.map(section=><MatchSection key={section.key} section={section} data={data}/>)}
 <Sheet className="space-y-3 p-5"><SectionTitle>Recent imports</SectionTitle>
  {data.runs.length===0?<p className="text-sm text-ink-3">No imports yet. Bills and payments are imported from the Bills and Payment vouchers pages.</p>:
  <div className="overflow-x-auto"><table className="w-full min-w-[36rem] text-left text-sm"><thead><tr className="text-meta text-ink-3"><th className="py-2 font-semibold">What</th><th className="font-semibold">Result</th><th className="font-semibold">By</th><th className="font-semibold">When</th></tr></thead><tbody>{data.runs.map(r=><tr key={r.id} className="border-t border-rule"><td className="py-2">{KINDS[r.kind]||r.kind}<span className="block text-meta text-ink-3">{r.files.join(' · ')}</span></td><td>{Object.entries(r.counts).filter(([,n])=>n).map(([k,n])=>`${n} ${COUNT_WORDS[k]||k}`).join(' · ')||'Nothing imported'}</td><td>{r.by}</td><td>{day(r.at)}</td></tr>)}</tbody></table></div>}
 </Sheet>
 </div>;
}
