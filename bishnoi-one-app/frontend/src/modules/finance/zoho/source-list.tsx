import Link from 'next/link';
import type {ReactNode} from 'react';
import {StatusPill, type PillTone} from '@/src/platform/ui/list-layout';
import {Empty} from '../platform/ui/sheet';
import {LinkButton} from '../platform/ui/button';

export function SourceNotice() {
  return <div role="note" className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-rule bg-bench px-4 py-3 text-sm text-ink-2">
    <StatusPill tone="plain">Zoho copy</StatusPill>
    <span>Read-only. Not posted to Finance accounting, receivables or BIR reports.</span>
  </div>;
}

export function SourceStatus({value}:{value:string}) {
  const status=value.toLowerCase();
  const tone:PillTone=['paid','closed','fulfilled'].includes(status)?'good':
    ['void','voided','cancelled','canceled'].includes(status)?'bad':
    ['overdue','partially_paid'].includes(status)?'warn':
    ['confirmed','sent','open'].includes(status)?'info':'plain';
  return <StatusPill tone={tone}>{value.replaceAll('_',' ')||'Status unavailable'}</StatusPill>;
}

export function SourcePeriod({company,period,q}:{company:string;period:string;q:string}) {
  return <form className="flex flex-wrap items-center gap-2" aria-label="Choose saved period">
    <input suppressHydrationWarning type="hidden" name="company" value={company}/>
    {q&&<input suppressHydrationWarning type="hidden" name="q" value={q}/>}
    <label className="sr-only" htmlFor="source-period">Saved period</label>
    <select suppressHydrationWarning id="source-period" name="period" defaultValue={period} className="h-9 rounded-xl border border-rule bg-white px-3 text-sm">
      <option value="month">This month</option><option value="q1">Q1 2026</option><option value="all">All saved dates</option>
    </select>
    <button suppressHydrationWarning className="h-9 rounded-xl border border-rule px-3 text-sm hover:bg-bench">Apply</button>
  </form>;
}

export function SourceEmpty({kind,filtered,savedCount,clear,canManage}:{kind:'orders'|'invoices';filtered:boolean;savedCount:number;clear:string;canManage:boolean}) {
  const noSaved=savedCount===0;
  const allDates=kind==='orders'?'/finance/sales-orders?company=all&period=all':'/finance/invoices/zoho?company=all&period=all';
  return <Empty title={noSaved?'No '+kind+' saved for this period':filtered?'No matching '+kind:'No '+kind+' to show'}
    actions={<>{noSaved?<LinkButton href={allDates}>Show all saved dates</LinkButton>:filtered&&<LinkButton href={clear}>Clear filters</LinkButton>}{canManage&&noSaved&&<LinkButton href="/finance/integrations/zoho">Check Zoho connection</LinkButton>}</>}>
    {noSaved?'Try All saved dates. If records are still missing, ask the Finance administrator to check the background update.':'Try another customer, company or saved period.'}
  </Empty>;
}

export function SourceRecordLink({href,children}:{href:string;children:ReactNode}) {
  return <Link href={href} className="font-medium text-hema hover:underline">{children}</Link>;
}
