"use client";
import {useState,useTransition} from 'react';
import {useRouter} from 'next/navigation';
import {Button} from '../platform/ui/button';
import {Field,Input,Select,Textarea,FormError} from '../platform/ui/field';
import {makeFormat} from '../platform/lib/format';
import type {Org} from '../platform/lib/types';
import type {SalesOrder,OrderLine} from './types';
import {saveOrder,orderStep} from './actions';

export function SalesOrderEditor({order,categories,org}:{order:SalesOrder|null;categories:{key:string;name:string}[];org:Org}){
 const fmt=makeFormat(org),router=useRouter();
 const [form,setForm]=useState({customerName:order?.customerName??'',customerTin:order?.customerTin??'',customerAddress:order?.customerAddress??'',orderDate:order?.date??fmt.todayKey(),reference:order?.reference??'',salesperson:order?.salesperson??'',termsDays:String(order?.termsDays??30),pricesIncludeTax:order?.pricesIncludeTax??true,notes:order?.notes??''});
 const blank=()=>({description:'',ref:'',quantity:'1',price:'',discount:'',category:'standard'});
 const [lines,setLines]=useState(order?order.lines.map(line=>({description:line.description??'',ref:line.ref??'',quantity:String(line.quantity),price:String(line.unitPriceCentavos/100),discount:String(line.discountCentavos/100),category:line.category})):[blank()]);
 const [error,setError]=useState<string|null>(null),[pending,start]=useTransition();
 const update=(key:keyof typeof form,value:string|boolean)=>setForm(current=>({...current,[key]:value}));
 return <form className="space-y-5" onSubmit={event=>{event.preventDefault();start(async()=>{
  setError(null);
  if(!form.customerName.trim())return setError('Enter the customer name.');
  const parsed:OrderLine[]=[];
  for(const [index,line] of lines.entries()){
   const price=fmt.toCentavos(line.price),discount=line.discount.trim()?fmt.toCentavos(line.discount):0,quantity=Number(line.quantity);
   if((!line.description.trim()&&!line.ref.trim())||!Number.isInteger(quantity)||quantity<1||price===null||price<0||discount===null||discount<0)return setError(`Line ${index+1}: enter an item, whole-number quantity, unit price and valid discount.`);
   parsed.push({description:line.description.trim()||null,ref:line.ref.trim()||null,quantity,unitPriceCentavos:price,discountCentavos:discount,category:line.category});
  }
  const result=await saveOrder(order?.id??null,{...form,customerName:form.customerName.trim(),customerTin:form.customerTin.trim()||null,customerAddress:form.customerAddress.trim()||null,reference:form.reference.trim()||null,salesperson:form.salesperson.trim()||null,notes:form.notes.trim()||null,termsDays:Number(form.termsDays),version:order?.version??1,lines:parsed});
  if(!result.ok)return setError(result.error);router.push(`/finance/sales-orders/${result.data.id}`);router.refresh();
 });}}>
 <fieldset disabled={pending} className="space-y-5"><div className="rounded-[3px] bg-sheet p-5 shadow-sheet"><div className="grid gap-4 sm:grid-cols-2">
 {([['customerName','Customer'],['customerTin','Customer TIN (optional)'],['customerAddress','Customer address (optional)'],['orderDate','Order date'],['reference','Customer PO / reference (optional)'],['salesperson','Sales rep (optional)'],['termsDays','Payment terms (days)']] as const).map(([key,label])=><Field key={key} label={label}>{props=><Input {...props} value={String(form[key])} required={key==='customerName'||key==='orderDate'} type={key==='orderDate'?'date':key==='termsDays'?'number':'text'} min={key==='termsDays'?0:undefined} max={key==='termsDays'?365:undefined} onChange={event=>update(key,event.target.value)} />}</Field>)}
 </div></div>
 <section className="space-y-3 rounded-[3px] bg-sheet p-5 shadow-sheet"><label className="flex gap-2 text-sm"><input suppressHydrationWarning type="checkbox" checked={form.pricesIncludeTax} onChange={event=>update('pricesIncludeTax',event.target.checked)}/>Prices include VAT</label><div className="overflow-x-auto"><table className="w-full min-w-[45rem] text-sm"><thead><tr className="text-left text-ink-3"><th>Item</th><th>Qty</th><th>Unit price</th><th>Discount</th><th>VAT</th><th/></tr></thead><tbody>{lines.map((line,index)=><tr key={index}>{(['description','quantity','price','discount'] as const).map(key=><td key={key} className="p-1"><Input aria-label={`Line ${index+1}: ${key}`} value={line[key]} inputMode={key==='description'?undefined:'decimal'} onChange={event=>setLines(current=>current.map((old,i)=>i===index?{...old,[key]:event.target.value}:old))}/></td>)}<td className="p-1"><Select aria-label={`Line ${index+1}: VAT`} value={line.category} onChange={event=>setLines(current=>current.map((old,i)=>i===index?{...old,category:event.target.value}:old))}>{categories.map(category=><option key={category.key} value={category.key}>{category.name}</option>)}</Select></td><td><Button size="sm" variant="quiet" disabled={lines.length===1} onClick={()=>setLines(current=>current.filter((_,i)=>i!==index))}>Remove</Button></td></tr>)}</tbody></table></div><Button size="sm" disabled={lines.length>=100} onClick={()=>setLines(current=>[...current,blank()])}>Add a line</Button><p className="text-meta text-ink-3">Totals are calculated on save using Finance's existing tax setup. Saving or approving an order does not issue an invoice.</p></section>
 <Field label="Notes (optional)">{props=><Textarea {...props} rows={3} maxLength={1000} value={form.notes} onChange={event=>update('notes',event.target.value)}/>}</Field><FormError message={error}/><div className="flex gap-2"><Button type="submit" variant="primary" loading={pending}>Save draft</Button><Button variant="quiet" onClick={()=>router.back()}>Cancel</Button></div></fieldset></form>;
}

export function SalesOrderSteps({order}:{order:SalesOrder}){
 const router=useRouter(),[pending,start]=useTransition(),[error,setError]=useState<string|null>(null);
 const [reason,setReason]=useState(''),[action,setAction]=useState<'return'|'cancel'|null>(null);
 function run(step:'submit'|'approve'|'return'|'cancel'){
  if((step==='return'||step==='cancel')&&reason.trim().length<3)return setError('Give a reason in a few words.');
  if((step==='submit'||step==='approve')&&!window.confirm(step==='approve'?'Approve this Sales Order in Finance only? This will not update Zoho, issue an invoice or release stock.':'Submit this Sales Order for approval in Finance?'))return;
  start(async()=>{setError(null);const result=await orderStep(order.id,step,order.version,reason);if(!result.ok){setError(result.error);router.refresh();return;}setAction(null);setReason('');router.refresh();});
 }
 return <div className="space-y-3"><FormError message={error}/>{action?<div className="space-y-2"><Field label={action==='return'?'What needs correction?':'Why cancel this order?'}>{props=><Input {...props} maxLength={300} value={reason} disabled={pending} onChange={event=>setReason(event.target.value)}/>}</Field><div className="flex gap-2"><Button variant="danger" loading={pending} onClick={()=>run(action)}>{action==='return'?'Return for correction':'Confirm cancellation'}</Button><Button disabled={pending} onClick={()=>{setAction(null);setError(null);}}>Keep order</Button></div></div>:<div className="flex flex-wrap gap-2">{order.canSubmit&&<Button variant="primary" loading={pending} onClick={()=>run('submit')}>Submit for approval</Button>}{order.canApprove&&<Button variant="primary" loading={pending} onClick={()=>run('approve')}>Approve in Finance</Button>}{order.canReturn&&<Button disabled={pending} onClick={()=>setAction('return')}>Return for correction</Button>}{order.canCancel&&<Button variant="quiet" disabled={pending} onClick={()=>setAction('cancel')}>Cancel order</Button>}</div>}</div>;
}
