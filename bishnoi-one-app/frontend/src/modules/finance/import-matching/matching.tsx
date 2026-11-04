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
import {RecordsModal} from './records';
import {day,money,readFiles,send,type Match,type Matching,type Proposal,type Section,type SourceFile} from './types';

// Settings → Import matching (app/routers/imports.py): each label in an import's exports is matched
// once. Whoever may confirm a section saves it in one step; others propose and it waits for them
// (tax labels: BIR and Compliance). Imports use confirmed matches only.

type Area='bills'|'oojeema'|'expenses';
const AREAS:{key:Area;label:string;says:string}[]=[
 {key:'bills',label:'Bills and supplier payments',says:'Choose both CSV files together: the Zoho Bills export and the Vendor Payments export.'},
 {key:'oojeema',label:'Oojeema sales',says:"Choose both CSV files together: Oojeema's Sales Journal and Receipt Journal. Match the accounts debited in the Receipt Journal; these can include non-cash settlements."},
 {key:'expenses',label:'Expenses',says:'Choose one CSV file: the Zoho Expenses export. After confirming the company labels, load it again: the other company\'s labels drop out.'},
];
const SECTIONS:{key:Section;role:string;area:Area;title:string;says:string;choice:string}[]=[
 {key:'company',role:'bill',area:'bills',title:'Company labels',says:'The company each label in the exports stands for.',choice:'Company'},
 {key:'account',role:'line',area:'bills',title:'Accounts on bill lines',says:'The Finance account and purchase type for each account used on Zoho bill lines.',choice:'Finance account and purchase type'},
 {key:'tax',role:'line',area:'bills',title:'Tax labels',says:'The VAT kind each Zoho tax label means. BIR and Compliance confirms these.',choice:'VAT kind'},
 {key:'money',role:'paid_from',area:'bills',title:'Paid-from accounts',says:'The Finance account each Zoho "paid through" account stands for.',choice:'Finance account'},
 {key:'money',role:'deposit_to',area:'oojeema',title:'Receipt accounts',says:"Match each Oojeema Account Name (DR) to its actual Finance account. All active chart accounts are offered here. Non-cash matches stay held from import until their settlement treatment is reviewed. Repeated names may belong to different company charts: check the code with Sir Mel. Bank numbers show only their last four digits.",choice:'Finance account'},
 {key:'company',role:'expense',area:'expenses',title:'Company labels on expenses',says:"The company each Zoho cost centre stands for. A person confirms this: a cost centre's name isn't proof of the company.",choice:'Company'},
 {key:'account',role:'expense',area:'expenses',title:'Expense accounts',says:'The Finance account and purchase type for each Zoho expense account.',choice:'Finance account and purchase type'},
 {key:'tax',role:'expense',area:'expenses',title:'Tax labels on expenses',says:'The VAT kind each Zoho tax label means on an expense. BIR and Compliance confirms these.',choice:'VAT kind'},
 {key:'money',role:'paid_through',area:'expenses',title:'Paid-through accounts',says:'The Finance account each Zoho "paid through" account stands for on an expense.',choice:'Finance account'},
];
const KINDS:Record<string,string>={bills:'Bills',supplier_payments:'Supplier payments',oojeema_sales:'Oojeema sales and receipts',expenses:'Expenses'};
const COUNT_WORDS:Record<string,string>={ready:'imported',held:'held',skipped:'skipped',imported:'already imported'};

/** What the row shows chosen: the person's unsaved choice, else what is saved. */
const chosenOf=(m:Match,draft?:Proposal):Proposal=>({accountId:m.accountId,purchaseType:m.purchaseType,vatKind:m.vatKind,company:m.company,note:'',perRecord:m.perRecord,...draft});
function complete(section:Section,p:Proposal){
 if(section==='company')return Boolean(p.company);
 if(p.perRecord)return true;
 if(section==='account')return Boolean(p.accountId&&p.purchaseType);
 if(section==='tax')return Boolean(p.vatKind);
 return Boolean(p.accountId);
}
function status(m:Match){
 if(m.status==='open')return m.note?`Not chosen yet. ${m.note}`:'Not chosen yet';
 if(m.status==='proposed')return `Proposed by ${m.proposedBy||'someone'} on ${day(m.proposedAt)}${m.waitingOn?` · waiting for ${m.waitingOn}`:''}`;
 if(m.automatic)return `Filled in automatically on ${day(m.confirmedAt)}. ${m.note??''}`;
 if(m.perRecord)return `Depends on the record (set by ${m.confirmedBy||'someone'} on ${day(m.confirmedAt)}): ${m.rules.confirmed} supplier or line ${m.rules.confirmed===1?'choice':'choices'}${m.rules.proposed?`, ${m.rules.proposed} waiting`:''}. Click the record count to choose.`;
 if(m.confirmedBy===m.proposedBy)return `Saved by ${m.confirmedBy||'someone'} on ${day(m.confirmedAt)}`;
 return `Confirmed by ${m.confirmedBy||'someone'} on ${day(m.confirmedAt)} (proposed by ${m.proposedBy||'someone'})`;
}

function MatchSection({section,data,files,onFiles}:{section:(typeof SECTIONS)[number];data:Matching;files:SourceFile[];onFiles:(files:SourceFile[])=>void}){
 const [drafts,setDrafts]=useState<Record<string,Proposal>>({}),[busy,setBusy]=useState<string|null>(null),[error,setError]=useState<string|null>(null),[viewing,setViewing]=useState<Match|null>(null);
 const rows=data.matches.filter(m=>m.section===section.key&&m.role===section.role);
 const counts={open:rows.filter(m=>m.status==='open').length,proposed:rows.filter(m=>m.status==='proposed').length,confirmed:rows.filter(m=>m.status==='confirmed').length};
 const {lineAccounts,moneyAccounts,receiptAccounts,purchaseTypes,vatKinds,companies}=data.choices;
 const edit=(m:Match,change:Proposal)=>setDrafts(d=>({...d,[m.id]:{...d[m.id],...change}}));
 const dirty=(m:Match)=>{const d=drafts[m.id];return Boolean(d&&((d.accountId!==undefined&&d.accountId!==m.accountId)||(d.purchaseType!==undefined&&d.purchaseType!==m.purchaseType)||(d.vatKind!==undefined&&d.vatKind!==m.vatKind)||(d.company!==undefined&&d.company!==m.company)||(d.perRecord!==undefined&&d.perRecord!==m.perRecord)||d.note));};
 async function propose(m:Match){
  if(m.status==='confirmed'&&!m.savesConfirmed&&!window.confirm('Changing a confirmed match sends it back for confirmation. Imports stop using it until someone who may confirm it does. Continue?'))return;
  const p=chosenOf(m,drafts[m.id]);
  const body:Proposal=section.key==='company'?{company:p.company}:p.perRecord?{perRecord:true}:section.key==='account'?{accountId:p.accountId,purchaseType:p.purchaseType}:section.key==='tax'?{vatKind:p.vatKind}:{accountId:p.accountId};
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
  // Sir Mel (2026-10-29): one Zoho label can stand for several of ours; then each line takes its
  // supplier's rule or its own choice, made from the records window.
  const depends=(section.key==='account'||section.key==='tax')&&<label className="flex items-center gap-2 text-meta text-ink-2"><input suppressHydrationWarning type="checkbox" disabled={off} checked={Boolean(p.perRecord)} onChange={e=>edit(m,{perRecord:e.target.checked})}/>Depends on the record (choose by supplier or line)</label>;
  if(p.perRecord)return depends;
  if(section.key==='company')return <Select aria-label={`Company for ${label}`} disabled={off} placeholder="Choose company" value={p.company??''} onChange={e=>edit(m,{company:e.target.value||null})}>{companies.map(c=><option key={c.key} value={c.key}>{c.label}</option>)}</Select>;
  if(section.key==='tax')return <div className="space-y-2"><Select aria-label={`VAT kind for ${label}`} disabled={off} placeholder="Choose VAT kind" value={p.vatKind??''} onChange={e=>edit(m,{vatKind:e.target.value||null})}>{vatKinds.map(c=><option key={c.key} value={c.key}>{c.label}</option>)}</Select>{depends}</div>;
  const receiptSection=section.area==='oojeema'&&section.role==='deposit_to';
  const accounts=receiptSection?receiptAccounts:section.key==='account'?lineAccounts:moneyAccounts;
  const picker=<SearchSelect className="w-full" aria-label={`Finance account for ${label}`} showSearch={{optionFilterProp:'label'}} allowClear disabled={off} placeholder="Choose the Finance account…" notFoundContent={receiptSection?"No active chart account matches. Try its code or check Accounting → Chart of accounts.":section.key==='account'?"No expense or asset account matches. Bill lines take expense and asset accounts only (as on the bill screen), so liabilities such as SSS Loans Payable aren't offered.":"No account under Cash matches."} value={p.accountId||undefined} options={accounts.map(a=>({value:a.id,label:`${a.code} · ${a.name}${receiptSection&&'type' in a?` · ${a.type}`:''}`}))} onChange={(value:string|undefined)=>edit(m,{accountId:value??null})}/>;
  if(section.key==='money')return picker;
  return <div className="space-y-2">{picker}<Select aria-label={`Purchase type for ${label}`} disabled={off} placeholder="Choose purchase type" value={p.purchaseType??''} onChange={e=>edit(m,{purchaseType:e.target.value||null})}>{purchaseTypes.map(c=><option key={c.key} value={c.key}>{c.label}</option>)}</Select>{depends}</div>;
 }
 return <ListFrame><div className="space-y-1 px-5 pt-4 pb-3"><SectionTitle>{section.title}</SectionTitle><p className="text-sm text-ink-2">{section.says}</p></div>
 <FigureStrip figures={[{label:'Open',value:String(counts.open)},{label:'Waiting for confirmation',value:String(counts.proposed)},{label:'Confirmed',value:String(counts.confirmed)}]}/>
 {error&&<div className="px-5 pt-3"><FormError message={error}/></div>}
 {rows.length===0?<p className="p-5 text-sm text-ink-3">No labels here yet.{data.may.propose?' Load the Zoho exports above.':''}</p>:
 <ExpandableTable minWidth="56rem" columns={[{key:'label',label:section.area==='oojeema'?'Oojeema debit account':'Zoho label'},{key:'records',label:'Records',align:'right'},{key:'amount',label:'Amount',align:'right'},{key:'choice',label:section.choice,className:'w-72'},{key:'status',label:'Status'}]} rows={rows.map(m=>{
  const p=chosenOf(m,drafts[m.id]),changed=dirty(m);
  return {id:m.id,cells:[
   <span key="label" className="font-medium">{m.sourceLabel||<span className="text-ink-3">Blank (no label in Zoho)</span>}{m.sourceCode&&<span className="block text-meta font-normal text-ink-3">{m.sourceCode}</span>}</span>,
   m.records>0?<button key="records" type="button" suppressHydrationWarning className="font-medium text-sage-deep underline underline-offset-2 hover:text-ink" title="See these records" onClick={()=>setViewing(m)}>{m.records}</button>:<span key="records" className="text-ink-3">0</span>,
   <span key="amount">{money(m.amountCentavos)}</span>,
   <div key="choice">{choice(m)}</div>,
   <span key="status" className="text-meta text-ink-2">{status(m)}{m.note&&<span className="block text-ink-3">Note: {m.note}</span>}{changed&&<span className="block text-due-today">Changed here, not proposed yet</span>}</span>,
  ],actions:<>{m.canPropose&&<Button size="sm" variant={m.status==='open'||changed?'primary':'default'} loading={busy===m.id} disabled={!complete(section.key,p)||(m.status!=='open'&&!changed)} title={m.savesConfirmed?'Your save is final; who and when are kept':m.status==='confirmed'?'Changing sends it back for confirmation':'Someone who may confirm it checks it next'} onClick={()=>propose(m)}>{m.status==='confirmed'?'Change':m.savesConfirmed?'Save':'Propose'}</Button>}{m.canConfirm&&<Button size="sm" variant="primary" disabled={busy===m.id||changed} title={changed?'Propose or undo your change first':undefined} onClick={()=>confirm(m)}>Confirm</Button>}</>,
  detail:<div className="grid gap-3 sm:grid-cols-2"><p className="text-sm">{status(m)}{m.mine&&m.status==='proposed'?'. Your proposal: someone else confirms it.':''}</p>{m.canPropose?<Field label="Note with your proposal" optional>{props=><Input {...props} maxLength={300} value={p.note??''} placeholder="Why this choice (optional)" onChange={e=>edit(m,{note:e.target.value})}/>}</Field>:<p className="text-meta text-ink-3">Only people who can propose matches change these.</p>}</div>};
 })}/>}
 {viewing&&<RecordsModal match={viewing} choices={data.choices} files={files} onFiles={onFiles} onClose={()=>setViewing(null)}/>}
 </ListFrame>;
}

export function ImportMatching({data}:{data:Matching}){
 const router=useRouter();
 const [picked,setPicked]=useState<File[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState<string|null>(null),[loaded,setLoaded]=useState<{labels:number;new:number}|null>(null),[files,setFiles]=useState<Partial<Record<Area,SourceFile[]>>>({}),[area,setArea]=useState<Area>('bills');
 const here=AREAS.find(a=>a.key===area)!;
 async function load(){
  setBusy(true);setError(null);setLoaded(null);
  try{const contents=await readFiles(picked);const done=await send<{labels:number;new:number;pack:string}>('/finance/import-matching/load',{files:contents});setLoaded(done);const packed=(done.pack==='oojeema'||done.pack==='expenses'?done.pack:'bills') as Area;setFiles(f=>({...f,[packed]:contents}));setArea(packed);setPicked([]);router.refresh();}
  catch(e){setError(e instanceof Error?e.message:'The exports could not be loaded.');}finally{setBusy(false);}
 }
 return <div className="space-y-5"><Sheet className="space-y-3 p-5">
  <p className="text-sm">Match each label from the Zoho exports once. What the export already says is filled in; same-name accounts are suggested. If you may confirm a section, your save is final; otherwise it waits for someone who may. Only confirmed matches are used by imports.</p>
  <p className="text-sm text-ink-2">Imported records post their control accounts (Accounts receivable and payable, Sales, Output and Input VAT, tax withheld) to Finance&apos;s default accounts, like any record entered here (<Link href="/platform/settings/finance/default-accounts" className="underline">Accounting → Default accounts</Link>).</p>
  <div className="flex flex-wrap gap-2">{AREAS.map(a=><Button key={a.key} size="sm" variant={area===a.key?'primary':'quiet'} onClick={()=>{setArea(a.key);setPicked([]);setError(null);setLoaded(null);}}>{a.label}</Button>)}</div>
  {!data.importsHere&&<p className="text-sm text-due-today">Imports run on the testing site for now; matching can still be prepared here.</p>}
 </Sheet>
 {data.may.propose&&<Sheet className="space-y-4 p-5"><SectionTitle>Load the exports</SectionTitle><p className="text-sm text-ink-2">{here.says} Labels already here keep their matches. Nothing is imported.</p>
  <Field label="CSV files" hint="Up to 16 MB together.">{props=><Input {...props} type="file" accept=".csv,text/csv" multiple disabled={busy} onChange={e=>{setPicked(Array.from(e.target.files||[]));setError(null);setLoaded(null);}}/>}</Field>
  <FormError message={error}/>
  <div className="flex flex-wrap items-center gap-3"><Button variant="primary" loading={busy} disabled={picked.length===0||picked.length>2} onClick={load}>Load the exports</Button><span className="text-meta text-ink-3">{picked.length?`${picked.length} ${picked.length===1?'file':'files'} selected`:'No files selected'}</span></div>
  {loaded&&<p role="status" className="text-sm font-medium">{loaded.labels} labels, {loaded.new} new.</p>}
 </Sheet>}
 {SECTIONS.filter(s=>s.area===area).map(section=><MatchSection key={`${section.key}-${section.role}`} section={section} data={data} files={files[area]??[]} onFiles={read=>setFiles(f=>({...f,[area]:read}))}/>)}
 <Sheet className="space-y-3 p-5"><SectionTitle>Recent imports</SectionTitle>
  {data.runs.length===0?<p className="text-sm text-ink-3">No imports yet. Each import has its button on its own page: Bills, Payment vouchers, Sales invoices, Imported expenses.</p>:
  <div className="overflow-x-auto"><table className="w-full min-w-[36rem] text-left text-sm"><thead><tr className="text-meta text-ink-3"><th className="py-2 font-semibold">What</th><th className="font-semibold">Result</th><th className="font-semibold">By</th><th className="font-semibold">When</th></tr></thead><tbody>{data.runs.map(r=><tr key={r.id} className="border-t border-rule"><td className="py-2">{KINDS[r.kind]||r.kind}<span className="block text-meta text-ink-3">{r.files.join(' · ')}</span></td><td>{Object.entries(r.counts).filter(([,n])=>n).map(([k,n])=>`${n} ${COUNT_WORDS[k]||k}`).join(' · ')||'Nothing imported'}</td><td>{r.by}</td><td>{day(r.at)}</td></tr>)}</tbody></table></div>}
 </Sheet>
 </div>;
}
