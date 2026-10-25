import { Search } from "lucide-react";
import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { Button } from "@/src/modules/pharmacy/platform/ui/button";
import { Input } from "@/src/modules/pharmacy/platform/ui/field";
import { Flag } from "@/src/modules/pharmacy/platform/ui/marks";
import { Empty, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { BATCH_STATUSES, MEDICINE_STATUSES, PRESCRIPTION_STATUSES, RX_CLASSES } from "@/src/modules/pharmacy/lib/words";
import type { BatchStatus, DispenseState, MaterialReviewStatus, MedicineStatus, PrescriptionStatus, RxClass, RxSource } from "@/src/modules/pharmacy/lib/types";

// The small pieces every Pharmacy screen shares. Status is printed in ink,
// never coloured: solid for the settled state, dashed for waiting, outlined
// for set aside, and the one red flag for what someone must act on.

const solid = "border border-ink bg-ink text-white";
const dashed = "border border-dashed border-ink-2 text-ink-2";
const outlined = "border border-rule-strong text-ink-3";

function Stamp({ style, children }: { style: string; children: ReactNode }) {
  return <span className={`inline-flex h-5 shrink-0 items-center rounded-[2px] px-1.5 text-stamp whitespace-nowrap uppercase ${style}`}>{children}</span>;
}

export function RxStatusMark({ status }: { status: PrescriptionStatus }) {
  if (status === "needs_clarification") return <Flag letter="?">{PRESCRIPTION_STATUSES[status]}</Flag>;
  if (status === "verified") return <Stamp style={solid}>{PRESCRIPTION_STATUSES[status]}</Stamp>;
  if (status === "rejected") return <Stamp style={outlined}>{PRESCRIPTION_STATUSES[status]}</Stamp>;
  return <Stamp style={dashed}>{PRESCRIPTION_STATUSES[status]}</Stamp>;
}

export const MATERIAL_REVIEW_STATUSES: Record<MaterialReviewStatus, string> = {
  waiting: "For review",
  approved: "Approved",
  returned: "Returned for changes",
  rejected: "Rejected",
};

export function MaterialReviewMark({ status }: { status: MaterialReviewStatus }) {
  if (status === "returned") return <Flag letter="?">{MATERIAL_REVIEW_STATUSES[status]}</Flag>;
  if (status === "approved") return <Stamp style={solid}>{MATERIAL_REVIEW_STATUSES[status]}</Stamp>;
  if (status === "rejected") return <Stamp style={outlined}>{MATERIAL_REVIEW_STATUSES[status]}</Stamp>;
  return <Stamp style={dashed}>{MATERIAL_REVIEW_STATUSES[status]}</Stamp>;
}

export function DispenseMark({ state }: { state: DispenseState }) {
  if (state === "full") return <Stamp style={solid}>Dispensed</Stamp>;
  if (state === "partial") return <Stamp style={dashed}>Partly dispensed</Stamp>;
  return <Stamp style={dashed}>To dispense</Stamp>;
}

/** The Bishnoi One app that sent a prescription in for checking, by the name people know it by. */
export function sourceName(app: string): string {
  return ({ crm: "Bishnoi One CRM", orders: "Bishnoi One Order", exec: "Bishnoi One Admin" } as Record<string, string>)[app] ?? app.toUpperCase();
}

/** Where a sent-in prescription came from: "From Bishnoi One CRM · Q-2026-00042 · sent by Rico Padilla". */
export function SourceMark({ source }: { source: RxSource }) {
  return (
    <span className="block text-meta text-ink-3">
      From {sourceName(source.app)}
      {source.reference && ` · ${source.reference}`}
      {source.sentBy && ` · sent by ${source.sentBy}`}
    </span>
  );
}

export function BatchStatusMark({ status, expired }: { status: BatchStatus; expired?: boolean }) {
  if (status === "recalled") return <Flag letter="!">{BATCH_STATUSES.recalled}</Flag>;
  if (status === "quarantined") return <Stamp style={dashed}>{BATCH_STATUSES.quarantined}</Stamp>;
  if (expired) return <Flag letter="!">Expired</Flag>;
  return <Stamp style={outlined}>{BATCH_STATUSES.available}</Stamp>;
}

export function RxClassMark({ rxClass }: { rxClass: RxClass }) {
  if (rxClass === "otc") return <Stamp style={outlined}>OTC</Stamp>;
  if (rxClass === "dangerous") return <Stamp style={solid}>DD · Rx</Stamp>;
  return <Stamp style={solid}>Rx</Stamp>;
}

export const rxClassTitle = (rxClass: RxClass) => RX_CLASSES[rxClass];

export function MedicineStatusMark({ status }: { status: MedicineStatus }) {
  if (status === "active") return null;
  return <Stamp style={status === "inactive" ? dashed : outlined}>{MEDICINE_STATUSES[status]}</Stamp>;
}

/** A section's own pages, as tabs under its title: Inbox, Pending, Verified... */
export function Tabs({ tabs, current, label }: { tabs: { href: string; label: string; count?: number; value: string }[]; current: string; label: string }) {
  return (
    <nav aria-label={label} className="mb-5 flex flex-wrap gap-x-6 gap-y-1 overflow-x-auto border-b border-rule">
      {tabs.map((t) => (
        <Link
          key={t.value}
          href={t.href}
          scroll={false}
          aria-current={t.value === current ? "page" : undefined}
          className={`-mb-px inline-flex items-center gap-1.5 border-b-2 px-1 pb-2 text-sm whitespace-nowrap ${
            t.value === current ? "border-hema font-semibold text-hema" : "border-transparent text-ink-2 hover:text-ink"
          }`}
        >
          {t.label}
          {t.count !== undefined && t.count > 0 && (
            <span className={`rounded-full px-1.5 text-meta tabular-nums ${t.value === current ? "bg-hema-tint" : "bg-bench text-ink-3"}`}>{t.count}</span>
          )}
        </Link>
      ))}
    </nav>
  );
}

/** A search that lives in the URL, keeping whatever else the page is filtered by. */
export function SearchBar({ q, placeholder, keep = {} }: { q: string; placeholder: string; keep?: Record<string, string> }) {
  return (
    <form className="flex max-w-md flex-1 items-end gap-2" role="search">
      {Object.entries(keep).map(([k, v]) => (
        <input suppressHydrationWarning key={k} type="hidden" name={k} value={v} />
      ))}
      <Input name="q" defaultValue={q} placeholder={placeholder} aria-label={placeholder} />
      <Button type="submit" size="sm" icon={<Search className="size-4" aria-hidden />}>
        Search
      </Button>
    </form>
  );
}

/** A labelled input for a server page's own GET form (date ranges, filters).
 *  `Field` takes a function as its child, which can't leave the server. */
export function FilterInput({ label, ...rest }: { label: string } & ComponentProps<"input">) {
  return (
    <label className="block min-w-0">
      <span className="mb-1 block text-meta font-medium text-ink-2">{label}</span>
      <Input {...rest} />
    </label>
  );
}

/** For a page someone's role doesn't open. */
export function NoAccess({ what }: { what: string }) {
  return (
    <Sheet>
      <Empty icon="roles" title={`Your role doesn't include ${what}`}>
        Ask an administrator if you need it.
      </Empty>
    </Sheet>
  );
}

/** A table's head row. */
export function Head({ columns }: { columns: (string | { label: string; right?: boolean; className?: string })[] }) {
  return (
    <thead>
      <tr className="border-b border-rule text-caps text-ink-3 uppercase">
        {columns.map((c, i) => {
          const col = typeof c === "string" ? { label: c } : c;
          return (
            <th
              key={col.label || i}
              scope="col"
              className={`py-3 font-semibold ${i === 0 ? "pl-5" : "pl-3"} ${i === columns.length - 1 ? "pr-5" : "pr-3"} ${col.right ? "text-right" : ""} ${col.className ?? ""}`}
            >
              {col.label}
            </th>
          );
        })}
      </tr>
    </thead>
  );
}

/** A number cell that dims zero. */
export function Qty({ n, unit }: { n: number; unit?: string }) {
  return (
    <span className={`tabular-nums ${n === 0 ? "text-ink-3" : ""}`}>
      {n.toLocaleString()}
      {unit && <span className="text-meta text-ink-3"> {unit}</span>}
    </span>
  );
}

/** "Due in 40 days", "Expired 12 days ago": how near an expiry date is. */
export function ExpiryWords({ days }: { days: number }) {
  if (days <= 0) return <Flag letter="!">{days === 0 ? "Expires today" : `Expired ${-days} day${days === -1 ? "" : "s"} ago`}</Flag>;
  return <span className={days <= 90 ? "font-semibold text-ink" : "text-ink-3"}>{days} day{days === 1 ? "" : "s"} left</span>;
}
