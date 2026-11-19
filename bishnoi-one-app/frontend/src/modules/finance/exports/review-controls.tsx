// Server-rendered download form. Existing screen filters travel with the file.
// Downloading is read-only; print/PDF controls remain independent.
export function ReviewExports({ filters, options, dates = true }: {
  filters: string; options: readonly (readonly [string, string])[]; dates?: boolean;
}) {
  const query = new URLSearchParams(filters);
  const control = "h-8 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm";
  return <section aria-label="Export for review" className="mb-4 min-w-0 rounded-xl border border-rule bg-sheet px-4 py-3 print:hidden">
    <form action="/finance/exports/review" className="flex flex-wrap items-end gap-3">
      <span className="self-center text-sm font-semibold text-ink">Export for review</span>
      {Array.from(query.entries()).filter(([key]) => !["kind", "start", "end"].includes(key)).map(([key,value]) => <input suppressHydrationWarning key={key} type="hidden" name={key} value={value} />)}
      <label className="grid gap-1 text-meta">File<select suppressHydrationWarning name="kind" className={control}>{options.map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      {dates && <><label className="grid gap-1 text-meta">Export from<input suppressHydrationWarning type="date" name="start" className={control} /></label><label className="grid gap-1 text-meta">Export to<input suppressHydrationWarning type="date" name="end" className={control} /></label></>}
      <button suppressHydrationWarning className={control + " font-semibold"} type="submit">Download CSV</button>
    </form>
    <p className="mt-2 text-meta text-ink-3">All matching records, including other pages. {dates && "Export dates affect this file only. Payments use their payment date."} Record totals and line details are separate files.</p>
  </section>;
}
