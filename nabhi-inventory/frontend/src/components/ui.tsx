import { Search } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Button } from "@/src/platform/ui/button";
import { Input } from "@/src/platform/ui/field";
import { Flag } from "@/src/platform/ui/marks";
import type { Expiry, StockState } from "../lib/types";
import { STOCK_STATES } from "../lib/labels";

// The pieces every Inventory screen is built from. Server components: the
// interactive ones are in their own "use client" files.

/** A place's tabs, as links so the tab lives in the address. Only the ones this person may open. */
export function Tabs({ label, tabs, current }: { label: string; tabs: { href: string; label: string; show?: boolean }[]; current: string }) {
  const shown = tabs.filter((t) => t.show !== false);
  if (shown.length < 2) return null;
  return (
    <nav aria-label={label} className="mb-5 flex flex-wrap gap-x-6 gap-y-1 border-b border-rule">
      {shown.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          aria-current={t.href === current ? "page" : undefined}
          className={`-mb-px border-b-2 px-1 pb-2 text-sm ${t.href === current ? "border-hema font-semibold text-hema" : "border-transparent text-ink-2 hover:text-ink"}`}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}

export type Tone = "neutral" | "active" | "done" | "attention" | "muted";

const TONES: Record<Tone, string> = {
  // Waiting on someone: dashed, like a form not yet signed.
  neutral: "border border-dashed border-ink-2 text-ink-2",
  active: "border border-hema bg-hema-tint text-hema",
  done: "border border-ink bg-ink text-white",
  attention: "border border-eosin text-eosin",
  muted: "border border-rule-strong text-ink-3",
};

/** A document's status, stamped. */
export function Stamp({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`inline-flex h-5 shrink-0 items-center rounded-[2px] px-1.5 text-stamp whitespace-nowrap uppercase ${TONES[tone]}`}>{children}</span>;
}

/** How much of a product there is, in a word. Only out and low draw the eye. */
export function StateMark({ state }: { state: StockState }) {
  if (!state) return <span className="text-meta text-ink-3">—</span>;
  if (state === "out") return <Flag letter="!">{STOCK_STATES.out}</Flag>;
  if (state === "low") return <Flag letter="↓">{STOCK_STATES.low}</Flag>;
  return <span className="text-meta text-ink-3">{STOCK_STATES[state]}</span>;
}

export function ExpiryMark({ expiry, label }: { expiry: Expiry; label: string }) {
  if (expiry === "expired") return <Flag letter="!">Expired {label}</Flag>;
  if (expiry === "expiring") return <Flag letter="⏱">{label}</Flag>;
  return <span className="text-ink-2">{label}</span>;
}

/** A table on a sheet, with room to scroll sideways on a phone. */
export function Table({ head, children, min = "40rem" }: { head: ReactNode[]; children: ReactNode; min?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm" style={{ minWidth: min }}>
        <thead>
          <tr className="border-b border-rule text-caps text-ink-3 uppercase">
            {head.map((h, i) => (
              <th key={i} scope="col" className={`px-3 py-3 font-semibold first:pl-5 last:pr-5 ${typeof h === "string" && h.startsWith(" ") ? "text-right" : ""}`}>
                {typeof h === "string" ? h.trim() : h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">{children}</tbody>
      </table>
    </div>
  );
}

/** A cell. `num` right-aligns figures so they line up. */
export function Td({ children, num, className = "" }: { children: ReactNode; num?: boolean; className?: string }) {
  return <td className={`px-3 py-2.5 align-top first:pl-5 last:pr-5 ${num ? "text-right whitespace-nowrap tabular-nums" : ""} ${className}`}>{children}</td>;
}

/** The first cell of a row that opens a record: its link stretches over the row. */
export function RowLink({ href, children, sub }: { href: string; children: ReactNode; sub?: ReactNode }) {
  return (
    <>
      <Link href={href} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
        {children}
      </Link>
      {sub && <span className="block text-meta text-ink-3">{sub}</span>}
    </>
  );
}

/** Search and filters, sent as the page's address (a plain GET form). */
export function Filters({ children, q, placeholder = "Search", keep = {} }: { children?: ReactNode; q?: string; placeholder?: string; keep?: Record<string, string> }) {
  return (
    <form role="search" className="mb-3 flex flex-wrap items-end gap-3">
      {Object.entries(keep).map(([k, v]) => v && <input key={k} type="hidden" name={k} value={v} />)}
      {q !== undefined && (
        <div className="w-full max-w-xs">
          <Input name="q" defaultValue={q} placeholder={placeholder} aria-label={placeholder} />
        </div>
      )}
      {children}
      <Button type="submit" size="sm" icon={<Search className="size-4" aria-hidden />}>
        Show
      </Button>
    </form>
  );
}

/** A plain select for a filter bar. */
export function FilterSelect({ name, value, label, options }: { name: string; value: string; label: string; options: { value: string; label: string }[] }) {
  return (
    <label className="block min-w-36">
      <span className="mb-1 block text-meta font-medium text-ink-2">{label}</span>
      <select name={name} defaultValue={value} className="h-9 w-full border-0 border-b border-control bg-transparent text-sm text-ink focus:border-hema focus:outline-none">
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Chip links for a list's quick filters: the one in use is filled. */
export function Chips({ options, current, label }: { options: { href: string; label: string; value: string }[]; current: string; label: string }) {
  return (
    <nav aria-label={label} className="mb-3 flex flex-wrap gap-1.5">
      {options.map((o) => (
        <Link
          key={o.value}
          href={o.href}
          scroll={false}
          aria-current={o.value === current ? "page" : undefined}
          className={`rounded-full border px-3 py-1 text-meta ${
            o.value === current ? "border-hema bg-hema-tint font-semibold text-hema" : "border-rule-strong bg-sheet text-ink-2 hover:border-hema hover:text-hema"
          }`}
        >
          {o.label}
        </Link>
      ))}
    </nav>
  );
}

/** The few numbers at the top of a record or a list, side by side. */
export function Figures({ items }: { items: { label: string; value: ReactNode; flag?: boolean; href?: string }[] }) {
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-[3px] bg-rule shadow-sheet sm:grid-cols-3 lg:grid-cols-6">
      {items.map((f) => (
        <div key={f.label} className="bg-sheet px-4 py-3">
          <dt className="text-meta text-ink-3">{f.flag ? <Flag letter="!">{f.label}</Flag> : f.label}</dt>
          <dd className="mt-0.5 text-lg font-semibold text-ink tabular-nums">
            {f.href ? (
              <Link href={f.href} className="hover:text-hema">
                {f.value}
              </Link>
            ) : (
              f.value
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** Shown in place of a page the role doesn't reach. */
export function NoAccess({ what }: { what: string }) {
  return (
    <div className="px-5 py-16 text-center">
      <p className="font-semibold text-ink-2">Your role doesn&apos;t include {what}.</p>
      <p className="mt-1 text-meta text-ink-3">Ask an administrator if you need it.</p>
    </div>
  );
}

/** Who did a step of a document, and when. */
export function Trail({ steps }: { steps: { label: string; who: { name: string } | null; when: string | null }[] }) {
  const done = steps.filter((s) => s.who || s.when);
  if (done.length === 0) return null;
  return (
    <ol className="flex flex-wrap gap-x-6 gap-y-2 text-meta">
      {done.map((s) => (
        <li key={s.label}>
          <span className="block text-ink-3">{s.label}</span>
          <span className="text-ink">{s.who?.name ?? "—"}</span>
          {s.when && <span className="text-ink-3"> · {s.when}</span>}
        </li>
      ))}
    </ol>
  );
}
