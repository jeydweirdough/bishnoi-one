import { Search } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Button } from "@/src/platform/ui/button";
import { Select } from "@/src/platform/ui/field";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { Flag } from "@/src/platform/ui/marks";
import type { Expiry, StockState } from "../lib/types";
import { STOCK_STATES } from "../lib/labels";

// The pieces every Inventory screen is built from. Server components: the
// interactive ones are in their own "use client" files.

export type Tone = "neutral" | "active" | "done" | "attention" | "muted";

// The CRM's status pills: waiting is grey, under way is mint, finished is
// sage, a problem is red, cancelled is faded. The words say it; the dot is for the eye.
const TONES: Record<Tone, string> = {
  neutral: "bg-[#f1f1ee] text-ink-2",
  active: "bg-hema-tint text-ink",
  done: "bg-[#e6f2e1] text-[#3f6f35]",
  attention: "bg-danger-tint text-danger",
  muted: "bg-bench text-ink-3",
};

/** A document's status, as a pill. */
export function Stamp({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex h-6 shrink-0 items-center gap-1.5 rounded-md px-2.5 text-meta font-medium whitespace-nowrap ${TONES[tone]}`}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {children}
    </span>
  );
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
          <tr className="border-b border-rule text-left text-meta text-ink-3">
            {head.map((h, i) => (
              <th key={i} scope="col" className={`px-3 py-2.5 font-medium first:pl-5 last:pr-5 ${typeof h === "string" && h.startsWith(" ") ? "text-right" : ""}`}>
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
      <Link href={href} className="font-semibold text-ink after:absolute after:inset-0 hover:underline">
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
        <label className="relative min-w-[14rem] flex-1">
          <span className="sr-only">{placeholder}</span>
          <Search className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
          <input
            type="search"
            name="q"
            defaultValue={q}
            placeholder={placeholder}
            className="block h-10 w-full rounded-lg border border-control bg-sheet pr-4 pl-11 text-sm text-ink placeholder:text-ink-3/80 transition-colors hover:border-ink-3 focus:border-ink focus:shadow-[0_0_0_3px_rgb(168_214_155_/_0.45)] focus:outline-none"
          />
        </label>
      )}
      {children}
      <Button type="submit" icon={<Search className="size-4" aria-hidden />}>
        Show
      </Button>
    </form>
  );
}

/** A plain select for a filter bar. */
export function FilterSelect({ name, value, label, options }: { name: string; value: string; label: string; options: { value: string; label: string }[] }) {
  return (
    <label className="block min-w-[10rem]">
      <span className="mb-1 block text-meta font-medium text-ink-2">{label}</span>
      <Select name={name} defaultValue={value}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </Select>
    </label>
  );
}

/** A list's quick filters: the CRM's segmented control, the one in use in ink. */
export function Chips({ options, current, label }: { options: { href: string; label: string; value: string }[]; current: string; label: string }) {
  return (
    <nav aria-label={label} className="mb-3 max-w-full overflow-x-auto">
      <ToggleLinks options={options} current={current} />
    </nav>
  );
}

/** The few numbers at the top of a record or a list, side by side. */
export function Figures({ items }: { items: { label: string; value: ReactNode; flag?: boolean; href?: string }[] }) {
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {items.map((f) => (
        <div key={f.label} className={`flex flex-col-reverse justify-end rounded-xl border bg-sheet px-5 py-4 ${f.flag ? "border-danger/40" : "border-rule"}`}>
          <dt className="mt-1 text-sm font-medium text-ink">{f.flag ? <Flag letter="!">{f.label}</Flag> : f.label}</dt>
          <dd className="text-[1.625rem] leading-tight font-semibold tracking-[-0.02em] text-ink tabular-nums">
            {f.href ? (
              <Link href={f.href} className="hover:text-ink">
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
