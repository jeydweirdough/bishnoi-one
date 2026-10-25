"use client";

import { Car, Motorbike, Pencil, Search, Trash2 } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { ConfirmButton } from "@/src/modules/admin/platform/ui/confirm";
import { Empty } from "@/src/modules/admin/platform/ui/sheet";
import type { IconName } from "@/src/modules/admin/platform/ui/icons";

/**
 * The CRM's table (Desktop: bishnoi-one-crm-components.html, "Table"): search
 * and one filter on top, the name links to the record with its actions beside
 * it, a page at a time. Every list in Executive Admin is one of these.
 */

export type Column<T> = {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
  /** "num" for figures (right-aligned), "hide-sm" for a column a phone can do without. */
  kind?: "num" | "hide-sm";
  width?: string;
};

export type TableFilter<T> = { label: string; options: Record<string, string>; matches: (row: T, key: string) => boolean };

const PAGE = 25;

export function RecordTable<T extends { id: string }>({
  rows,
  columns,
  search,
  searchLabel,
  filter,
  empty,
  emptyIcon = "lists",
  rowTone,
}: {
  rows: T[];
  columns: Column<T>[];
  /** The words a row is found by. */
  search: (row: T) => string;
  searchLabel: string;
  filter?: TableFilter<T>;
  empty: { title: string; body: ReactNode };
  emptyIcon?: IconName;
  /** A row that needs attention is tinted, as the CRM marks a visit overdue. */
  rowTone?: (row: T) => "bad" | null;
}) {
  const [q, setQ] = useState("");
  const [pick, setPick] = useState("all");
  const [page, setPage] = useState(0);

  const shown = useMemo(() => {
    const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return rows.filter((r) => (pick === "all" || !filter || filter.matches(r, pick)) && words.every((w) => search(r).toLowerCase().includes(w)));
  }, [rows, q, pick, filter, search]);
  const pages = Math.max(1, Math.ceil(shown.length / PAGE));
  const at = Math.min(page, pages - 1);
  const slice = shown.slice(at * PAGE, at * PAGE + PAGE);

  return (
    <div className="overflow-hidden rounded-[22px] border border-rule bg-sheet">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-4 py-4 sm:px-[18px]">
        <label className="relative w-80 max-w-full">
          <span className="sr-only">{searchLabel}</span>
          <Search className="pointer-events-none absolute top-1/2 left-4 size-[18px] -translate-y-1/2 text-ink-3" aria-hidden />
          <input suppressHydrationWarning
            value={q}
            onChange={(e) => (setQ(e.target.value), setPage(0))}
            placeholder={searchLabel}
            className="h-10 w-full rounded-full border border-control bg-sheet pr-4 pl-11 text-sm placeholder:text-ink-3 hover:border-ink-3 focus:border-ink focus:ring-3 focus:ring-mint-2 focus:outline-none"
          />
        </label>
        {filter && (
          <div role="group" aria-label={filter.label} className="inline-flex flex-wrap gap-0.5 rounded-full border border-rule bg-sheet p-1">
            {[["all", "All"] as const, ...Object.entries(filter.options)].map(([key, label]) => {
              const n = key === "all" ? rows.length : rows.filter((r) => filter.matches(r, key)).length;
              return (
                <button suppressHydrationWarning
                  key={key}
                  type="button"
                  aria-pressed={pick === key}
                  onClick={() => (setPick(key), setPage(0))}
                  className={`rounded-full px-4 py-[7px] text-[13px] transition-colors ${pick === key ? "bg-ink text-white" : "text-ink-2 hover:bg-mint hover:text-ink"}`}
                >
                  {label}
                  <span className="ml-1.5 text-[11.5px] opacity-70">{n}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {slice.length === 0 ? (
        <Empty title={rows.length === 0 ? empty.title : "Nothing matches"} icon={emptyIcon}>
          {rows.length === 0 ? empty.body : "Try other words, or show all."}
        </Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {columns.map((c) => (
                  <th
                    key={c.key}
                    scope="col"
                    style={c.width ? { width: c.width } : undefined}
                    className={`border-b border-rule bg-[#fbfbfa] px-[18px] py-3 text-left text-[12px] font-medium whitespace-nowrap text-ink-3 ${c.kind === "num" ? "text-right" : ""} ${c.kind === "hide-sm" ? "hidden md:table-cell" : ""}`}
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {slice.map((r) => (
                <tr key={r.id} className={`border-b border-rule last:border-0 hover:bg-mint ${rowTone?.(r) === "bad" ? "bg-danger-tint/30" : ""}`}>
                  {columns.map((c) => (
                    <td key={c.key} className={`px-[18px] py-3.5 align-middle ${c.kind === "num" ? "text-right tabular-nums" : ""} ${c.kind === "hide-sm" ? "hidden md:table-cell" : ""}`}>
                      {c.render(r)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {shown.length > 0 && (
        <div className="flex items-center justify-between border-t border-rule px-[18px] py-3 text-[13px] text-ink-3">
          <span>
            {at * PAGE + 1}–{Math.min(shown.length, at * PAGE + PAGE)} of {shown.length}
          </span>
          {pages > 1 && (
            <div className="flex gap-1">
              <PagerButton label="Previous" disabled={at === 0} onClick={() => setPage(at - 1)}>
                ‹
              </PagerButton>
              {Array.from({ length: pages }, (_, i) => (
                <PagerButton key={i} label={`Page ${i + 1}`} current={i === at} onClick={() => setPage(i)}>
                  {i + 1}
                </PagerButton>
              ))}
              <PagerButton label="Next" disabled={at === pages - 1} onClick={() => setPage(at + 1)}>
                ›
              </PagerButton>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PagerButton({ children, label, current, disabled, onClick }: { children: ReactNode; label: string; current?: boolean; disabled?: boolean; onClick: () => void }) {
  return (
    <button suppressHydrationWarning
      type="button"
      aria-label={label}
      aria-current={current ? "page" : undefined}
      disabled={disabled}
      onClick={onClick}
      className={`grid size-[34px] place-items-center rounded-full ${current ? "bg-ink text-white" : "text-ink-2 hover:bg-mint disabled:opacity-40 disabled:hover:bg-transparent"}`}
    >
      {children}
    </button>
  );
}

/** The CRM's round initials beside a name: filled for what matters now, outlined for the rest. */
/** What a record is, drawn in its circle instead of letters: a car or a motorcycle. */
export type Glyph = "car" | "motorcycle";
const GLYPHS: Record<Glyph, { icon: typeof Car; label: string }> = { car: { icon: Car, label: "Car" }, motorcycle: { icon: Motorbike, label: "Motorcycle" } };

export function Initials({ name, filled = false, glyph }: { name: string; filled?: boolean; glyph?: Glyph }) {
  if (glyph) {
    const { icon: I, label } = GLYPHS[glyph];
    return (
      <span title={label} className={`grid size-9 shrink-0 place-items-center rounded-full border-[1.5px] border-ink ${filled ? "bg-sage" : "bg-sheet"}`}>
        <I className="size-[18px]" aria-label={label} />
      </span>
    );
  }
  const letters = name
    .replace(/^(dr|dra|ms|mr|sir)\.?\s+/i, "")
    .split(/\s+/)
    .filter((w) => /^[a-z0-9]/i.test(w))
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
  return (
    <span aria-hidden className={`grid size-9 shrink-0 place-items-center rounded-full border-[1.5px] border-ink text-[12.5px] font-semibold ${filled ? "bg-sage" : "bg-sheet"}`}>
      {letters || "•"}
    </span>
  );
}

/** The CRM's tags: the word always says it; the colour only helps. */
export function Tag({ tone = "outline", dot = false, children }: { tone?: "outline" | "good" | "warn" | "bad" | "info" | "mute"; dot?: boolean; children: ReactNode }) {
  const look = {
    outline: "border border-ink bg-sheet text-ink",
    good: "bg-[#e6f2e1] text-[#3f6f35]",
    warn: "bg-[#fbf0d9] text-[#8a5a00]",
    bad: "bg-danger-tint text-danger",
    info: "bg-[#e7eef8] text-[#1f4f8a]",
    mute: "bg-[#f0f0ee] text-ink-2",
  }[tone];
  return (
    <span className={`inline-flex h-[26px] items-center gap-1.5 rounded-full px-3 text-[12.5px] font-medium whitespace-nowrap ${look}`}>
      {dot && <span className="size-[7px] rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

/** A date in a cell, with how far it is under it, coloured only when it matters. */
export function DueCell({ date, days, note }: { date: string | null; days: number | null; note?: string }) {
  if (!date) return <span className="text-ink-3">Not set</span>;
  const shown = new Date(`${date.slice(0, 10)}T00:00:00`).toLocaleDateString("en-PH", { day: "numeric", month: "short", year: "numeric" });
  const how =
    days === null ? note ?? "" : days < 0 ? `${Math.abs(days)} ${Math.abs(days) === 1 ? "day" : "days"} overdue` : days === 0 ? "today" : days === 1 ? "tomorrow" : days <= 60 ? `in ${days} days` : (note ?? "");
  return (
    <span className="block whitespace-nowrap">
      {shown}
      {how && <span className={`block text-[12.5px] ${days !== null && days < 0 ? "font-medium text-danger" : days !== null && days <= 30 ? "font-medium text-[#8a5a00]" : "text-ink-3"}`}>{how}</span>}
    </span>
  );
}

/**
 * The first cell of a row: initials, the name (and a line under it), and the
 * row's change and delete beside the name, as the CRM puts them.
 */
export function NameCell({
  name,
  sub,
  filled,
  initials,
  onEdit,
  onDelete,
  what,
}: {
  name: string;
  sub?: ReactNode;
  filled?: boolean;
  /** What the round mark says, when it isn't the name's initials (a request's number). */
  initials?: string;
  onEdit?: () => void;
  onDelete?: () => Promise<boolean | void>;
  /** "permit": for the buttons' words. */
  what: string;
}) {
  return (
    <span className="flex items-center gap-3">
      {initials ? (
        <span aria-hidden className={`grid size-9 shrink-0 place-items-center rounded-full border-[1.5px] border-ink text-[11px] font-semibold ${filled ? "bg-sage" : "bg-sheet"}`}>
          {initials}
        </span>
      ) : (
        <Initials name={name} filled={filled} />
      )}
      <span className="min-w-0">
        <span className="flex flex-wrap items-center gap-x-1">
          {onEdit ? (
            <button suppressHydrationWarning type="button" onClick={onEdit} className="text-left font-semibold text-ink hover:underline">
              {name}
            </button>
          ) : (
            <span className="font-semibold text-ink">{name}</span>
          )}
          {onEdit && (
            <button suppressHydrationWarning type="button" onClick={onEdit} aria-label={`Change ${name}`} title={`Change ${what}`} className="grid size-7 place-items-center rounded-full text-ink-3 hover:bg-sheet hover:text-ink">
              <Pencil className="size-3.5" aria-hidden />
            </button>
          )}
          {onDelete && (
            <ConfirmButton
              label={<span className="sr-only">Delete {name}</span>}
              icon={<Trash2 className="size-3.5" aria-hidden />}
              triggerTitle={`Delete ${what}`}
              triggerVariant="quiet"
              triggerSize="sm"
              triggerClassName="!size-7 !px-0 !text-ink-3 hover:!bg-danger/10 hover:!text-danger"
              title={`Delete ${name}?`}
              body={`This ${what} and its alerts are deleted. This can't be undone.`}
              confirmLabel={`Delete ${what}`}
              danger
              onConfirm={onDelete}
            />
          )}
        </span>
        {sub && <span className="block text-[12.5px] text-ink-3">{sub}</span>}
      </span>
    </span>
  );
}
