import { Search } from "lucide-react";
import type { ReactNode } from "react";
import { PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";

// The interface comes first, the records after. The sidebar and top bar never
// leave; the moment a link is clicked the page's own title, its search and
// filters and its cards are drawn (loading.tsx passes the real `title`), and
// only where records will be is there a pulse. A screen that streams its data
// (ui/later.tsx) uses the same pieces (ListRows, Lines, Pairs, Chart) inside
// its real cards, so nothing moves when the data lands.

/** A grey bar where text is about to be. */
export function Bone({ className = "" }: { className?: string }) {
  return <span aria-hidden className={`block animate-pulse rounded-[2px] bg-rule/70 ${className}`} />;
}

/** A grey area where a picture, chart or map is about to be. */
function Block({ className = "" }: { className?: string }) {
  return <span aria-hidden className={`block animate-pulse rounded-[3px] bg-rule/50 ${className}`} />;
}

const WIDTHS = ["w-full", "w-5/6", "w-2/3", "w-3/4", "w-1/2"];
const width = (i: number) => WIDTHS[i % WIDTHS.length];
const range = (n: number) => Array.from({ length: n }, (_, i) => i);

export function Lines({ rows }: { rows: number }) {
  return (
    <div className="space-y-3">
      {range(rows).map((i) => (
        <Bone key={i} className={`h-3.5 ${width(i % 3)}`} />
      ))}
    </div>
  );
}

/** Announced once to screen readers; everything inside is decoration. */
function Loading({ children }: { children: ReactNode }) {
  return (
    <div role="status" aria-label="Loading">
      <span className="sr-only">Loading…</span>
      {children}
    </div>
  );
}

/** The page header: the real title when the route knows it (a record's name is data, so it pulses). */
function Header({ title, crumbs = false, sub = true }: { title?: string; crumbs?: boolean; sub?: boolean }) {
  if (title)
    return (
      <>
        {crumbs && <Bone className="mb-2 h-3 w-40" />}
        <PageHeader title={title}>{sub && <Bone className="mt-1 h-3.5 w-64 max-w-full" />}</PageHeader>
      </>
    );
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0 flex-1">
        {crumbs && <Bone className="mb-2 h-3 w-40" />}
        <Bone className="h-7 w-64 max-w-full" />
        {sub && <Bone className="mt-2 h-3.5 w-80 max-w-full" />}
      </div>
    </div>
  );
}

/** A row of figure cards (count, value, change). */
export function Figures({ n }: { n: number }) {
  return (
    <div className={`mb-5 grid gap-3 sm:grid-cols-2 ${n >= 4 ? "lg:grid-cols-4" : "lg:grid-cols-3"}`}>
      {range(n).map((i) => (
        <Sheet key={i} className="px-5 py-4">
          <Bone className="h-3 w-24" />
          <Bone className="mt-3 h-7 w-28" />
          <Bone className="mt-2 h-3 w-20" />
        </Sheet>
      ))}
    </div>
  );
}

/** The search box and quick filters above a list or board, drawn as themselves (waiting, not yet usable). */
function Toolbar() {
  return (
    <div className="mb-4 flex flex-wrap items-end gap-3" aria-hidden>
      <div className="relative min-w-[14rem] flex-1">
        <Search className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-ink-3" />
        <input type="search" disabled placeholder="Search" tabIndex={-1} className="block h-10 w-full rounded-[3px] border border-control bg-sheet pr-4 pl-11 text-sm placeholder:text-ink-3/80" />
      </div>
      <span className="h-10 w-40 rounded-[3px] border border-control bg-sheet max-sm:hidden" />
    </div>
  );
}

/** Bars rising from a baseline: a chart is coming. */
export function Chart({ bars = 12 }: { bars?: number }) {
  const heights = ["h-1/3", "h-1/2", "h-2/3", "h-2/5", "h-3/4", "h-1/2", "h-4/5", "h-3/5"];
  return (
    <div className="flex h-44 items-end gap-2 border-b border-rule pb-px">
      {range(bars).map((i) => (
        <span key={i} aria-hidden className={`flex-1 animate-pulse rounded-t-md bg-rule/60 ${heights[i % heights.length]}`} />
      ))}
    </div>
  );
}

/** A table: its header, then rows with a name and a few short columns. */
function Table({ columns, rows }: { columns: number; rows: number }) {
  return (
    <div>
      <div className="grid gap-4 border-b border-rule px-5 py-3" style={{ gridTemplateColumns: `minmax(0,2fr) repeat(${columns - 1}, minmax(0,1fr))` }}>
        {range(columns).map((c) => (
          <Bone key={c} className={`h-3 ${c === 0 ? "w-24" : "w-16"}`} />
        ))}
      </div>
      {range(rows).map((r) => (
        <div key={r} className="grid gap-4 border-b border-rule px-5 py-3.5 last:border-0" style={{ gridTemplateColumns: `minmax(0,2fr) repeat(${columns - 1}, minmax(0,1fr))` }}>
          <div className="flex min-w-0 items-center gap-3">
            <span aria-hidden className="size-8 shrink-0 animate-pulse rounded-full bg-rule/60" />
            <div className="min-w-0 flex-1">
              <Bone className={`h-3.5 ${width(r)}`} />
              <Bone className="mt-1.5 h-3 w-1/2" />
            </div>
          </div>
          {range(columns - 1).map((c) => (
            <Bone key={c} className={`h-3.5 self-center ${width(r + c + 1)}`} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Rows of a list on the way, inside the list's own card: a name with a line under it, a few short columns. */
export function ListRows({ rows = 8, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div role="status" aria-label="Loading" className="divide-y divide-rule">
      <span className="sr-only">Loading…</span>
      {range(rows).map((r) => (
        <div key={r} className="grid gap-4 px-5 py-3.5" style={{ gridTemplateColumns: `minmax(0,2fr) repeat(${columns - 1}, minmax(0,1fr))` }}>
          <div className="min-w-0">
            <Bone className={`h-3.5 ${width(r)}`} />
            <Bone className="mt-1.5 h-3 w-1/2" />
          </div>
          {range(columns - 1).map((c) => (
            <Bone key={c} className={`h-3.5 self-center ${width(r + c + 1)}`} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Label and value pairs, as a record's details read. */
export function Pairs({ rows }: { rows: number }) {
  return (
    <div className="divide-y divide-rule">
      {range(rows).map((i) => (
        <div key={i} className="grid grid-cols-[9.5rem_minmax(0,1fr)] gap-4 py-2.5">
          <Bone className="h-3 w-24" />
          <Bone className={`h-3.5 ${width(i + 1)}`} />
        </div>
      ))}
    </div>
  );
}

/** A form's fields: a label over each box, two to a row. */
function Fields({ n }: { n: number }) {
  return (
    <div className="grid gap-x-4 gap-y-4 sm:grid-cols-2">
      {range(n).map((i) => (
        <div key={i}>
          <Bone className="mb-2 h-3 w-24" />
          <Bone className="h-9 w-full" />
        </div>
      ))}
    </div>
  );
}

function SectionHead() {
  return <Bone className="mb-4 h-3.5 w-36" />;
}

/** The old all-purpose shape, kept for a page with none of its own. */
export function PageSkeleton({ title, aside = true }: { title?: string; aside?: boolean }) {
  return (
    <Loading>
      <Header title={title} />
      <div className={aside ? "grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start" : ""}>
        <div className="space-y-5">
          <Sheet className="px-5 py-5">
            <SectionHead />
            <Lines rows={6} />
          </Sheet>
          <Sheet className="px-5 py-5">
            <SectionHead />
            <Lines rows={4} />
          </Sheet>
        </div>
        {aside && (
          <Sheet className="px-5 py-5 max-lg:hidden">
            <SectionHead />
            <Lines rows={5} />
          </Sheet>
        )}
      </div>
    </Loading>
  );
}

/** A list page: header with its New button, search and filters, a table, the pager. */
export function ListSkeleton({ title, figures = 0, columns = 5, rows = 8, chart = false }: { title?: string; figures?: number; columns?: number; rows?: number; chart?: boolean }) {
  return (
    <Loading>
      <Header title={title} />
      {figures > 0 && <Figures n={figures} />}
      {chart && (
        <Sheet className="mb-5 px-5 py-5">
          <SectionHead />
          <Chart />
        </Sheet>
      )}
      <Toolbar />
      <Sheet>
        <Table columns={columns} rows={rows} />
      </Sheet>
      <div className="mt-4 flex items-center justify-between">
        <Bone className="h-3 w-32" />
        <Bone className="h-8 w-48" />
      </div>
    </Loading>
  );
}

/** A board: a column per status, each with a few cards. */
export function BoardSkeleton({ title, columns = 4 }: { title?: string; columns?: number }) {
  return (
    <Loading>
      <Header title={title} />
      <Toolbar />
      <div className="grid auto-cols-[minmax(13rem,1fr)] grid-flow-col gap-3 overflow-hidden">
        {range(columns).map((c) => (
          <div key={c} className="min-h-[24rem] rounded-[3px] border border-rule p-2">
            <div className="mb-3 flex items-center gap-2 px-1.5 pt-1">
              <span aria-hidden className="size-6 animate-pulse rounded-md bg-rule/60" />
              <Bone className="h-3.5 w-20" />
              <Bone className="ml-auto h-3 w-6" />
            </div>
            <div className="space-y-2">
              {range(3 - (c % 2)).map((k) => (
                <Sheet key={k} className="px-3 py-3">
                  <Bone className={`h-3.5 ${width(c + k)}`} />
                  <Bone className="mt-2 h-3 w-1/2" />
                  <div className="mt-3 flex items-center justify-between">
                    <Bone className="h-3 w-16" />
                    <Bone className="h-3 w-12" />
                  </div>
                </Sheet>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Loading>
  );
}

/** One record: breadcrumb and title, its figures, its details and history beside a side panel. */
export function RecordSkeleton({ title, figures = 3, picture = false }: { title?: string; figures?: number; picture?: boolean }) {
  return (
    <Loading>
      <Header title={title} crumbs />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="space-y-5">
          {figures > 0 && (
            <Sheet className="grid divide-rule sm:grid-cols-3 sm:divide-x">
              {range(figures).map((i) => (
                <div key={i} className="px-5 py-4">
                  <Bone className="h-3 w-20" />
                  <Bone className="mt-3 h-6 w-24" />
                </div>
              ))}
            </Sheet>
          )}
          <Sheet className="px-5 py-5">
            {picture ? (
              <div className="grid gap-5 sm:grid-cols-[12rem_minmax(0,1fr)]">
                <Block className="aspect-square" />
                <div>
                  <SectionHead />
                  <Pairs rows={6} />
                </div>
              </div>
            ) : (
              <>
                <SectionHead />
                <Pairs rows={6} />
              </>
            )}
          </Sheet>
          <Sheet>
            <div className="px-5 pt-5">
              <SectionHead />
            </div>
            <Table columns={4} rows={4} />
          </Sheet>
        </div>
        <div className="space-y-5 max-lg:hidden">
          <Sheet className="px-5 py-5">
            <SectionHead />
            <Pairs rows={4} />
          </Sheet>
          <Sheet className="px-5 py-5">
            <SectionHead />
            <Lines rows={4} />
          </Sheet>
        </div>
      </div>
    </Loading>
  );
}

/** A form: breadcrumb and title, sections of fields, its buttons at the end; a summary beside it where the form has one. */
export function FormSkeleton({ title, sections = 2, summary = false, lines = false }: { title?: string; sections?: number; summary?: boolean; lines?: boolean }) {
  return (
    <Loading>
      <Header title={title} crumbs />
      <div className={summary ? "grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start" : "max-w-3xl"}>
        <div className="space-y-5">
          {range(sections).map((s) => (
            <Sheet key={s} className="px-5 py-5">
              <SectionHead />
              <Fields n={s === 0 ? 6 : 4} />
            </Sheet>
          ))}
          {lines && (
            <Sheet>
              <div className="px-5 pt-5">
                <SectionHead />
              </div>
              <Table columns={5} rows={3} />
            </Sheet>
          )}
          {!summary && (
            <div className="flex justify-end gap-2">
              <Bone className="h-9 w-24" />
              <Bone className="h-9 w-32" />
            </div>
          )}
        </div>
        {summary && (
          <Sheet className="px-5 py-5 max-lg:hidden">
            <SectionHead />
            <Pairs rows={4} />
            <Bone className="mt-5 h-10 w-full" />
          </Sheet>
        )}
      </div>
    </Loading>
  );
}

/** Home: a greeting, the figures, a chart, then two lists side by side. */
export function DashboardSkeleton({ title, figures = 4 }: { title?: string; figures?: number }) {
  return (
    <Loading>
      <Header title={title} />
      <Figures n={figures} />
      <Sheet className="mb-5 px-5 py-5">
        <div className="mb-4 flex items-center justify-between">
          <Bone className="h-3.5 w-36" />
          <Bone className="h-8 w-40" />
        </div>
        <Chart />
      </Sheet>
      <div className="grid gap-5 lg:grid-cols-2">
        {range(2).map((i) => (
          <Sheet key={i} className="px-5 py-5">
            <SectionHead />
            <div className="space-y-3.5">
              {range(5).map((r) => (
                <div key={r} className="flex items-center gap-3">
                  <span aria-hidden className="size-8 shrink-0 animate-pulse rounded-full bg-rule/60" />
                  <Bone className={`h-3.5 flex-1 ${width(r + i)}`} />
                  <Bone className="h-3 w-14" />
                </div>
              ))}
            </div>
          </Sheet>
        ))}
      </div>
    </Loading>
  );
}

/** A person's profile: the band with their picture and name, the tabs, then their figures. */
export function ProfileSkeleton() {
  return (
    <Loading>
      <Sheet className="mb-5 overflow-hidden">
        <Block className="h-28 rounded-none" />
        <div className="flex items-end gap-4 px-5 pb-5">
          <span aria-hidden className="-mt-10 size-20 shrink-0 animate-pulse rounded-full border-4 border-sheet bg-rule" />
          <div className="flex-1 pb-1">
            <Bone className="h-6 w-48" />
            <Bone className="mt-2 h-3.5 w-32" />
          </div>
          <Bone className="h-9 w-28" />
        </div>
      </Sheet>
      <div className="mb-5 flex gap-4 border-b border-rule pb-3">
        {range(3).map((i) => (
          <Bone key={i} className="h-3.5 w-20" />
        ))}
      </div>
      <Figures n={4} />
      <Sheet className="px-5 py-5">
        <SectionHead />
        <Chart bars={7} />
      </Sheet>
    </Loading>
  );
}

/** Settings: sections down the page, each a heading, a line saying what it's for, and its entries. */
export function SettingsSkeleton({ title, sections = 2 }: { title?: string; sections?: number }) {
  return (
    <Loading>
      <Header title={title} />
      <div className="max-w-4xl space-y-5">
        {range(sections).map((s) => (
          <Sheet key={s} className="px-5 py-5">
            <Bone className="h-4 w-40" />
            <Bone className="mt-2 mb-5 h-3 w-72 max-w-full" />
            <div className="divide-y divide-rule">
              {range(4).map((r) => (
                <div key={r} className="flex items-center justify-between gap-4 py-3">
                  <Bone className={`h-3.5 ${width(r + s)} max-w-xs`} />
                  <Bone className="h-8 w-20" />
                </div>
              ))}
            </div>
          </Sheet>
        ))}
      </div>
    </Loading>
  );
}

/** A month: the toolbar, then the days as a grid. */
export function CalendarSkeleton({ title }: { title?: string }) {
  return (
    <Loading>
      <Header title={title} />
      <Toolbar />
      <Sheet className="overflow-hidden">
        <div className="grid grid-cols-7 border-b border-rule">
          {range(7).map((d) => (
            <div key={d} className="px-3 py-2.5">
              <Bone className="h-3 w-8" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {range(35).map((d) => (
            <div key={d} className="h-24 border-r border-b border-rule p-2 [&:nth-child(7n)]:border-r-0">
              <Bone className="h-3 w-5" />
              {d % 4 === 1 && <Bone className="mt-2 h-4 w-full" />}
            </div>
          ))}
        </div>
      </Sheet>
    </Loading>
  );
}

/** Fields on the left, a map on the right (logging a visit, the transfers map). */
export function MapSkeleton({ title, fields = true }: { title?: string; fields?: boolean }) {
  return (
    <Loading>
      <Header title={title} crumbs />
      <div className={fields ? "grid gap-5 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]" : ""}>
        {fields && (
          <Sheet className="px-5 py-5">
            <SectionHead />
            <div className="space-y-4">
              {range(6).map((i) => (
                <div key={i}>
                  <Bone className="mb-2 h-3 w-24" />
                  <Bone className="h-9 w-full" />
                </div>
              ))}
            </div>
          </Sheet>
        )}
        <Block className="min-h-[32rem]" />
      </div>
    </Loading>
  );
}

/** An import: the steps across the top, then the place to drop the file. */
export function ImportSkeleton({ title }: { title?: string }) {
  return (
    <Loading>
      <Header title={title} crumbs />
      <div className="mb-5 flex items-center gap-3">
        {range(4).map((i) => (
          <div key={i} className="flex flex-1 items-center gap-2">
            <span aria-hidden className="size-7 shrink-0 animate-pulse rounded-[2px] bg-rule/70" />
            <Bone className="h-3 w-20 max-sm:hidden" />
          </div>
        ))}
      </div>
      <Sheet className="px-5 py-5">
        <div className="grid h-56 place-items-center rounded-[3px] border-[1.5px] border-dashed border-rule">
          <div className="flex flex-col items-center gap-3">
            <span aria-hidden className="size-10 animate-pulse rounded-lg bg-rule/60" />
            <Bone className="h-3.5 w-56" />
            <Bone className="h-3 w-32" />
          </div>
        </div>
      </Sheet>
    </Loading>
  );
}
