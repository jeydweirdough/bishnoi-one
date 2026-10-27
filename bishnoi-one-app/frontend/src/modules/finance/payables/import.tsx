"use client";
import { Upload } from "lucide-react";
import { useRef, useState, useTransition } from "react";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { FormError, Input } from "@/src/modules/finance/platform/ui/field";
import { checkSupplierImport, importSuppliers } from "./actions";
import { supplierFile, type SupplierRow, type ColumnCoverage } from "./csv";
import type { SupplierImportCheck } from "./types";

/** Directory first, using the existing inline panel and six-column table. */
export function SupplierImport() {
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<SupplierRow[]>([]);
  const [coverage, setCoverage] = useState<ColumnCoverage[]>([]);
  const [fileName, setFileName] = useState("");
  const [check, setCheck] = useState<SupplierImportCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [done, setDone] = useState<{ added: number; counts?: Record<string, number> } | null>(null);
  const [busy, start] = useTransition();
  const [query, setQuery] = useState("");
  const [exceptions, setExceptions] = useState(false);
  const [page, setPage] = useState(0);
  async function preview(source = rows) {
    setConfirmed(false); setError(null);
    const result = await checkSupplierImport(source);
    if (!result.ok) { setError(result.error); setUncertain(true); return; }
    setCheck(result.data); setUncertain(false); setPage(0);
  }
  function choose(file: File | undefined) {
    if (!file) return;
    start(async () => {
      setCheck(null); setRows([]); setCoverage([]); setError(null); setDone(null); setConfirmed(false); setUncertain(false); setQuery(""); setExceptions(false); setFileName(file.name);
      try {
        const parsed = supplierFile(await file.text());
        if (!parsed || !parsed.rows.length || parsed.rows.length > 3000) throw new Error("Choose a vendor CSV with a name column and 1 to 3,000 supplier rows.");
        setRows(parsed.rows); setCoverage(parsed.coverage); await preview(parsed.rows);
      } catch (error) { setError(error instanceof Error ? error.message : "Could not read this file."); }
    });
  }
  const matching = check?.rows.filter(row => (!exceptions || row.status !== "new") && `${row.supplier.name} ${row.supplier.tin ?? ""} ${row.record}`.toLowerCase().includes(query.toLowerCase())) ?? [];
  const visible = matching.slice(page * 50, page * 50 + 50);
  const included = check?.rows.filter(row => row.status === "new") ?? [];
  if (!open) return <Button icon={<Upload className="size-4" aria-hidden />} onClick={() => setOpen(true)}>Import from a file</Button>;
  return <section className="space-y-4 rounded-[3px] border border-rule bg-sheet p-4" aria-busy={busy}>
    <div><p className="text-sm font-semibold">Import suppliers</p><p className="text-meta text-ink-2">Bring in the supplier directory now. No individual tax reviews are required here. Missing or questionable details are kept for later; tax choices are confirmed when recording real bills. Existing suppliers stay unchanged. Bills, payments and opening balances are not imported.</p></div>
    <div className="flex flex-wrap items-center gap-3"><input suppressHydrationWarning ref={input} type="file" accept=".csv,text/csv" className="sr-only" aria-label="Pick the CSV file" disabled={busy} onChange={event => choose(event.target.files?.[0])} /><Button icon={<Upload className="size-4" aria-hidden />} loading={busy} onClick={() => input.current?.click()}>{fileName ? "Pick another file" : "Pick the CSV file"}</Button>{fileName && <span className="text-meta text-ink-2">{fileName}</span>}</div>
    <FormError message={error} />
    {done ? <div role="status" className="space-y-2 text-sm"><p className="font-semibold">{done.added} suppliers added to the directory.</p><p>{Object.entries(done.counts ?? {}).filter(([key]) => key !== "new").map(([key, count]) => `${count} ${key === "here" ? "already here" : key === "problem" ? "unusable" : key}`).join(" · ")}. No bills or payments were created.</p><Button onClick={() => { setOpen(false); setDone(null); setCheck(null); setRows([]); }}>Done</Button></div> : check && <>
      <p className="text-sm" aria-live="polite"><span className="font-semibold text-hema">{check.counts.new} to import</span> · {check.counts.here} already here · {check.counts.duplicate} repeated · {check.counts.conflict ?? 0} identity conflicts · {check.counts.problem} unusable.</p>
      <p className="text-meta text-ink-2">{included.filter(row => !row.supplier.tin).length} included suppliers have no usable TIN yet. All imported tax defaults remain unconfirmed. You can import without opening any row below.</p>
      <details><summary className="cursor-pointer text-sm font-medium">Optional: column coverage and excluded fields</summary><div className="max-h-60 overflow-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>Column</th><th>Populated rows</th><th>Handling</th></tr></thead><tbody>{coverage.map(column => <tr key={column.heading} className="border-t border-rule"><td>{column.heading}</td><td>{column.populated}</td><td>{column.populated ? column.treatment : "Empty"}</td></tr>)}</tbody></table></div><p className="text-meta">Tax/account/address hints and unresolved values are retained on imported suppliers. Source IDs and unmapped columns are excluded; source-ID matching remains a separate feature.</p></details>
      <details><summary className="cursor-pointer text-sm font-medium">Optional: suppliers and exceptions</summary>
        <div className="my-3 flex flex-wrap items-center gap-3"><label className="text-meta">Find supplier or record<Input value={query} onChange={event => { setQuery(event.target.value); setPage(0); }} /></label><label className="flex gap-2 text-sm"><input suppressHydrationWarning type="checkbox" checked={exceptions} onChange={event => { setExceptions(event.target.checked); setPage(0); }} />Exceptions only</label></div>
        <div className="max-h-[32rem] overflow-auto rounded-[3px] border border-rule"><table className="w-full min-w-[60rem] text-sm"><thead className="sticky top-0 bg-sheet"><tr className="border-b border-rule text-left text-caps text-ink-3 uppercase"><th className="w-10 py-2 pl-3">Included</th><th className="px-2 py-2 font-semibold">Name</th><th className="w-36 px-2 py-2 font-semibold">TIN</th><th className="px-2 py-2 font-semibold">Email · phone</th><th className="w-20 px-2 py-2 font-semibold">Terms</th><th className="w-72 py-2 pr-3 pl-2 font-semibold">What happens</th></tr></thead><tbody className="divide-y divide-rule">{visible.map(row => { const s = row.supplier; return <tr key={row.line} className="align-top"><td className="py-1.5 pl-3"><input suppressHydrationWarning type="checkbox" checked={row.status === "new"} disabled aria-label={`Record ${row.record}: ${row.status === "new" ? "included automatically" : "excluded automatically"}`} className="size-4 accent-hema" /></td><td className="px-2 py-1.5">{s.name || "No usable name"}<span className="block text-meta text-ink-3">Record {row.record}</span>{s.companyName && s.companyName !== s.name && <span className="block text-meta">{s.companyName}</span>}</td><td className="px-2 py-1.5 font-mono text-meta">{s.tin ? `${s.tin}-${s.branchCode}` : "Not available yet"}</td><td className="px-2 py-1.5 text-meta">{[s.email, s.phone, s.mobile, ...s.contacts.map(contact => contact.phone)].filter(Boolean).join(" · ") || "—"}</td><td className="px-2 py-1.5 text-meta">{s.termsDays} days</td><td className="py-1.5 pr-3 pl-2 text-meta">{row.note}</td></tr>; })}</tbody></table>{!visible.length && <p className="p-3 text-sm">No matching rows.</p>}</div>
        <div className="mt-2 flex items-center gap-3 text-meta"><span>{matching.length} matching rows · page {page + 1}</span><Button size="sm" disabled={!page} onClick={() => setPage(value => value - 1)}>Previous</Button><Button size="sm" disabled={(page + 1) * 50 >= matching.length} onClick={() => setPage(value => value + 1)}>Next</Button></div>
      </details>
      <label className="flex gap-2 text-sm"><input suppressHydrationWarning type="checkbox" checked={confirmed} disabled={busy || uncertain || !included.length} onChange={event => setConfirmed(event.target.checked)} />Import the directory with incomplete details retained. Exclude existing, repeated, conflicting and unusable rows. Confirm accounting details when these suppliers are used.</label>
      <div className="flex gap-2"><Button variant="primary" loading={busy} disabled={!confirmed || uncertain || !included.length} onClick={() => start(async () => { setError(null); const result = await importSuppliers(rows); if (!result.ok) { setError(`${result.error} Recheck before trying again; the outcome may need verification.`); setUncertain(true); setConfirmed(false); return; } setDone(result.data); })}>Import {included.length} suppliers</Button><Button disabled={busy} onClick={() => start(() => preview())}>Recheck summary</Button><Button variant="quiet" disabled={busy} onClick={() => setOpen(false)}>Cancel</Button></div>
    </>}
    {!check && !done && <Button variant="quiet" disabled={busy} onClick={() => setOpen(false)}>Cancel</Button>}
  </section>;
}
