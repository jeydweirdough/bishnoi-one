"use client";
import Link from "next/link";
import { useState,useTransition } from "react";
import { Button,buttonClass } from "@/src/modules/finance/platform/ui/button";
import { screen } from "@/src/modules/finance/lib/links";
import { linkPurchaseSupplier,returnPurchase,resumePurchase,cancelPurchaseDraft } from "./purchase-actions";
import { PURCHASE_STATES,type PurchaseIntake,type PurchaseQueue } from "./purchase-types";

export function PurchaseQueueView({queue}:{queue:PurchaseQueue}) {
  const [selected,setSelected]=useState<string[]>([]);
  const picks=queue.items.filter(x=>selected.includes(x.id));
  const compatible=picks.length>0 && picks.every(x=>x.supplier?.id===picks[0].supplier?.id && x.snapshot.currencyEvidence===picks[0].snapshot.currencyEvidence && x.holds.length===0 && x.remaining>0);
  return <section className="space-y-4">
    <p>On this page: {queue.items.filter(x=>x.remaining>0).length} receipts with quantities still waiting for bill preparation. {queue.total} received receipts in total. These are evidence, not posted bills. Selection applies to this page.</p>
    {queue.canPrepare && <div className="flex flex-wrap items-center gap-3"><span>{picks.length} receipts selected</span>{compatible?<Link className={buttonClass("primary")} href={screen(`/purchase-intakes/prepare?ids=${encodeURIComponent(selected.join(','))}`)}>Prepare one supplier invoice</Link>:<span className="text-sm">Select reviewed receipts for the same supplier and currency.</span>}</div>}
    <div className="overflow-x-auto"><table className="w-full min-w-[42rem] text-left text-sm"><caption className="sr-only">Received purchases waiting for Finance</caption><thead><tr><th>Select</th><th>Receipt / PO</th><th>Vendor</th><th>Status</th><th>Units remaining</th><th>Action</th></tr></thead><tbody>{queue.items.map(x=><tr key={x.id} className="border-t border-rule">
      <td className="p-2">{queue.canPrepare&&<input type="checkbox" aria-label={`Select receipt ${x.snapshot.receiptNumber}`} checked={selected.includes(x.id)} onChange={e=>setSelected(e.target.checked?[...selected,x.id]:selected.filter(id=>id!==x.id))}/>}</td>
      <td className="p-2">{x.snapshot.receiptNumber}<br/>{x.snapshot.orderNumber}</td><td className="p-2">{x.supplier?.name??x.snapshot.supplierName}</td><td className="p-2">{PURCHASE_STATES[x.state]??x.state}{x.holds.map(h=><p key={h} className="text-danger">{h}</p>)}</td><td className="p-2">{x.remaining}</td><td className="p-2"><Link className="font-semibold underline" href={screen(`/purchase-intakes/${x.id}`)}>Review</Link></td>
    </tr>)}</tbody></table></div><nav aria-label="Received purchase pages" className="flex gap-4">{queue.offset>0&&<Link className="underline" href={screen(`/purchase-intakes?offset=${Math.max(0,queue.offset-queue.limit)}`)}>Previous receipts</Link>}{queue.offset+queue.limit<queue.total&&<Link className="underline" href={screen(`/purchase-intakes?offset=${queue.offset+queue.limit}`)}>Next receipts</Link>}</nav>{!queue.items.length&&<p>No receipts have been sent from Inventory. Receiving alone does not send them; the receiver uses Turn into a Bill in Finance on the completed receipt.</p>}
  </section>;
}

export function PurchaseReview({item,suppliers,canLink,canPrepare}:{item:PurchaseIntake;suppliers:{id:string;name:string}[];canLink:boolean;canPrepare:boolean}) {
  const [reviewNote,setReviewNote]=useState('');const [supplier,setSupplier]=useState('');const [evidence,setEvidence]=useState('');const [reason,setReason]=useState('');const [error,setError]=useState('');const [busy,start]=useTransition();
  return <section className="space-y-4">
    <p>{PURCHASE_STATES[item.state]??item.state} · {item.remaining} units unallocated</p>{item.holds.map(h=><p key={h} role="status" className="rounded border border-rule p-3">{h}</p>)}
    <div className="flex flex-wrap gap-4"><Link className="underline" href={`/inventory/receipts/${item.snapshot.receiptId}`}>Open Inventory receipt</Link><Link className="underline" href={`/inventory/purchase-orders/${item.snapshot.orderId}`}>Open purchase order</Link></div>
    <p>Delivery reference: {item.snapshot.deliveryRef||'Not supplied'}. This does not certify the supplier invoice number. Source currency evidence: {item.snapshot.currencyEvidence}; Finance must verify invoice prices and currency.</p>
    <ul>{item.lines.map(ln=><li key={ln.id}>{ln.product}: received {ln.quantity} {ln.unit}; allocated {ln.allocated}; remaining {ln.remaining}.</li>)}</ul>
    {!item.supplier&&canLink&&<form className="space-y-3 rounded border border-rule p-4" onSubmit={e=>{e.preventDefault();start(async()=>{const r=await linkPurchaseSupplier(item.id,item.version,supplier,evidence);setError(r.ok?'':r.error);});}}><label className="grid gap-1">Verified 2MG supplier<select value={supplier} onChange={e=>setSupplier(e.target.value)} required><option value="">Choose the reviewed supplier</option>{suppliers.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label className="grid gap-1">Identity evidence checked<input value={evidence} onChange={e=>setEvidence(e.target.value)} minLength={3} maxLength={300} required placeholder="Explain the tax identity / branch evidence checked"/></label><Button type="submit" variant="primary" loading={busy}>Confirm source supplier link</Button></form>}
    {canPrepare&&item.supplier&&item.holds.length===0&&item.remaining>0&&<Link className={buttonClass("primary")} href={screen(`/purchase-intakes/prepare?ids=${item.id}`)}>Prepare supplier invoice</Link>}
    {canPrepare&&<form className="space-y-2" onSubmit={e=>{e.preventDefault();start(async()=>{const r=await returnPurchase(item.id,item.version,reason);setError(r.ok?'':r.error);});}}><label className="grid gap-1">Receiving correction needed<textarea value={reason} onChange={e=>setReason(e.target.value)} minLength={3} maxLength={300} required/></label><Button type="submit" loading={busy}>Return to receiving with reason</Button></form>}
    {canPrepare&&item.state==='needs_correction'&&!item.sourceConflict&&<form className="space-y-2 rounded border border-rule p-3" onSubmit={e=>{e.preventDefault();start(async()=>{const r=await resumePurchase(item.id,item.version,reviewNote);setError(r.ok?'':r.error);});}}><label className="grid gap-1">Review note: original received evidence verified unchanged<input value={reviewNote} onChange={e=>setReviewNote(e.target.value)} minLength={3} maxLength={300} required/></label><Button type="submit" loading={busy}>Resume Finance preparation after review</Button></form>}
    {!!error&&<p role="alert" className="text-danger">{error}</p>}
    {item.bills.map(b=><p key={b.id}><Link className="underline" href={screen(`/bills/${b.id}`)}>Open bill {b.number}</Link> · {b.state}</p>)}
  </section>;
}

export function CancelPurchaseDraft({id}:{id:string}) {
  const [error,setError]=useState('');const [busy,start]=useTransition();
  return <div><Button loading={busy} onClick={()=>start(async()=>{const r=await cancelPurchaseDraft(id);setError(r.ok?'':r.error);})}>Cancel this unsubmitted draft and release its quantities</Button>{!!error&&<p role="alert">{error}</p>}</div>;
}
