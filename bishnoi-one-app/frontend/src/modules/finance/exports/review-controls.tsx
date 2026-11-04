// Server-rendered download form. Existing screen filters travel with the file.
// Downloading is read-only; print/PDF controls remain independent.
export function ReviewExports({ filters, options, dates = true }: {
  filters: string; options: readonly (readonly [string, string])[]; dates?: boolean;
}) {
  const query = new URLSearchParams(filters);
  const control = "h-8 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm";
  return <details className="mb-4 print:hidden">
    <summary className="cursor-pointer text-sm font-semibold text-hema">Export for review</summary>
    <form action="/finance/exports/review" className="mt-3 flex flex-wrap items-end gap-3">
      {Array.from(query.entries()).filter(([key]) => !["kind", "start", "end"].includes(key)).map(([key,value]) => <input suppressHydrationWarning key={key} type="hidden" name={key} value={value} />)}
      <label className="grid gap-1 text-meta">File<select suppressHydrationWarning name="kind" className={control}>{options.map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      {dates && <><label className="grid gap-1 text-meta">Export from<input suppressHydrationWarning type="date" name="start" className={control} /></label><label className="grid gap-1 text-meta">Export to<input suppressHydrationWarning type="date" name="end" className={control} /></label></>}
      <button suppressHydrationWarning className={control + " font-semibold"} type="submit">Download CSV</button>
    </form>
    <p className="mt-2 text-meta text-ink-3">Uses the current search and status filters, including all matching records beyond the visible page. {dates && "Dates filter this download only; blank dates include all matching dates. Payments use their payment date."} Amounts are numeric; record totals and line details are separate files.</p>
  </details>;
}
