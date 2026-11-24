"use client";
import Link from "next/link";
import {useState,useTransition} from "react";
import {useRouter} from "next/navigation";
import {Button} from "@/src/modules/inventory/platform/ui/button";
import {sendReceiptToFinance} from "@/src/modules/inventory/actions/inventory";

export type ReceiptFinance = {state:string;reason:string|null;canSend:boolean;remaining:number;sentBy:string|null;sentAt:string|null;version:number;bills:{id:string;state:string}[]};
const states:Record<string,string>={not_sent:'Not sent to Finance',sending:'Waiting to reach Finance',received:'Waiting for Finance validation',held:'Finance review needed',needs_correction:'Receiving correction requested',partially_allocated:'Partly prepared in Finance',allocated:'Bill prepared in Finance'};
export function ReceiptFinancePanel({id,status}:{id:string;status:ReceiptFinance}) {
  const router=useRouter();const [busy,start]=useTransition();const [error,setError]=useState('');
  return <section aria-label="Finance handoff" className="mb-4 space-y-3 rounded border border-rule bg-sheet p-4">
    <h2 className="font-semibold">Finance</h2><p role="status">{states[status.state]??status.state}{status.state!=='not_sent'&&` · ${status.remaining} units not yet allocated to bills`}</p>
    <p className="text-sm">Send the quantities received to Finance for bill preparation. Finance will validate before approval or payment. Stock is received only once.</p>
    {status.reason&&<p role="status" className="text-sm">{status.reason}</p>}
    <div className="flex flex-wrap gap-3"><Button variant="primary" disabled={!status.canSend} loading={busy} onClick={()=>start(async()=>{setError('');const r=await sendReceiptToFinance(id);if(!r.ok)setError(r.error);router.refresh();})}>{status.state==='not_sent'?'Turn into a Bill in Finance':'Check / retry this saved handoff'}</Button><Button variant="quiet" onClick={()=>router.refresh()}>Refresh Finance status</Button></div>
    {!status.canSend&&status.state==='not_sent'&&!status.reason&&<p className="text-sm">Sending requires the approved Send received purchases to Finance permission.</p>}
    {status.sentBy&&<p className="text-sm">Sent by {status.sentBy}. Finance receipt is confirmed only when its status returns here.</p>}
    {status.bills.map(b=><p key={b.id}><Link className="underline" href={`/finance/bills/${b.id}`}>Open linked Finance bill</Link> · {b.state}. Finance access is checked when opening it.</p>)}
    {error&&<p role="alert" className="text-danger">{error} Refresh status before starting another action.</p>}
  </section>;
}
