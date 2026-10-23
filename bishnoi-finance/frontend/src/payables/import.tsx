"use client";

import { Upload } from "lucide-react";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { FormError } from "@/src/platform/ui/field";
import { checkSupplierImport, importSuppliers } from "./actions";
import { supplierRows } from "./csv";
import type { SupplierImportCheck, SupplierImportRow } from "./types";

const STATUS: Record<SupplierImportRow["status"], { label: string; tone: string }> = {
  new: { label: "New", tone: "bg-hema-tint text-hema" },
  here: { label: "Already here", tone: "bg-bench text-ink-2" },
  problem: { label: "Needs a look", tone: "bg-danger-tint text-danger" },
};

/**
 * Importing suppliers from Zoho's vendor export (CSV), decided 2026-10-23. The file is read here
 * in the browser; its rows are checked by the API and shown as they'd be saved (Zoho's Company
 * ID as the TIN when it is one, terms as days, inactive vendors switched off). New rows are
 * ticked; Import adds the ticked ones all or none. What's owed them isn't brought in.
 */
export function SupplierImport() {
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [fileName, setFileName] = useState("");
  const [check, setCheck] = useState<SupplierImportCheck | null>(null);
  const [ticked, setTicked] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [reading, read] = useTransition();
  const [importing, run] = useTransition();

  const importable = (r: SupplierImportRow) => r.status === "new";
  const chosen = check ? check.rows.filter((r) => ticked.has(r.line) && importable(r)) : [];

  function reset() {
    setCheck(null);
    setTicked(new Set());
    setError(null);
    setFileName("");
    if (input.current) input.current.value = "";
  }

  function choose(file: File | undefined) {
    if (!file) return;
    read(async () => {
      reset();
      setFileName(file.name);
      const rows = supplierRows(await file.text());
      if (!rows) return setError("This file has no name column. Export the vendors from Zoho as CSV (All Vendors → ⋯ → Export), with its headings.");
      if (!rows.length) return setError("The file has headings but no suppliers.");
      if (rows.length > 3000) return setError("The file has over 3,000 rows: split it, and import each part.");
      const result = await checkSupplierImport(rows);
      if (!result.ok) return setError(result.error);
      setCheck(result.data);
      setTicked(new Set(result.data.rows.filter(importable).map((r) => r.line)));
    });
  }

  function tick(line: number, on: boolean) {
    const next = new Set(ticked);
    if (on) next.add(line);
    else next.delete(line);
    setTicked(next);
  }

  function go() {
    run(async () => {
      const result = await importSuppliers(chosen.map((r) => r.supplier));
      if (!result.ok) return setError(result.error);
      toast.success(`${result.data.added} suppliers imported`, { description: "Set each one's VAT status and usual tax withheld when you next open them." });
      reset();
      setOpen(false);
    });
  }

  if (!open) {
    return (
      <Button icon={<Upload className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        Import from a file
      </Button>
    );
  }

  return (
    <section className="space-y-4 rounded-[3px] border border-rule bg-sheet p-4">
      <div>
        <p className="text-sm font-semibold">Import suppliers</p>
        <p className="text-meta text-ink-2">
          Zoho&apos;s vendor export as CSV (All Vendors → ⋯ → Export). The file is read here and not kept. Nothing is added until you press Import; suppliers
          already here (same name, or same TIN) are left as they are. Not brought in: what&apos;s owed them (an opening balance), their VAT status and the tax
          usually withheld (Zoho&apos;s export doesn&apos;t carry them the BIR&apos;s way): set those on each supplier after.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" aria-label="Pick the CSV file" onChange={(e) => choose(e.target.files?.[0])} />
        <Button icon={<Upload className="size-4" aria-hidden />} loading={reading} onClick={() => input.current?.click()}>
          {fileName ? "Pick another file" : "Pick the CSV file"}
        </Button>
        {fileName && <span className="text-meta text-ink-2">{fileName}</span>}
      </div>
      <FormError message={error} />

      {check && (
        <>
          <p className="text-sm">
            <span className="font-semibold text-hema">{check.counts.new} new</span> · {check.counts.here} already here ·{" "}
            <span className={check.counts.problem ? "font-semibold text-danger" : ""}>{check.counts.problem} need a look</span>. {chosen.length} ticked to import.
          </p>
          <div className="max-h-[32rem] overflow-auto rounded-[3px] border border-rule">
            <table className="w-full min-w-[60rem] text-sm">
              <thead className="sticky top-0 bg-sheet">
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th className="w-10 py-2 pl-3">
                    <input
                      type="checkbox"
                      aria-label="Tick every new supplier"
                      checked={chosen.length > 0 && chosen.length === check.rows.filter(importable).length}
                      onChange={(e) => setTicked(new Set(e.target.checked ? check.rows.filter(importable).map((r) => r.line) : []))}
                      className="size-4 accent-hema"
                    />
                  </th>
                  <th className="px-2 py-2 font-semibold">Name</th>
                  <th className="w-36 px-2 py-2 font-semibold">TIN</th>
                  <th className="px-2 py-2 font-semibold">Email · phone</th>
                  <th className="w-20 px-2 py-2 font-semibold">Terms</th>
                  <th className="w-72 py-2 pr-3 pl-2 font-semibold">What happens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {check.rows.map((r) => {
                  const s = r.supplier;
                  return (
                    <tr key={r.line} className={`align-top ${r.status === "here" ? "text-ink-3" : ""}`}>
                      <td className="py-1.5 pl-3">
                        <input
                          type="checkbox"
                          aria-label={`Import line ${r.line}: ${s.name}`}
                          disabled={!importable(r)}
                          checked={importable(r) && ticked.has(r.line)}
                          onChange={(e) => tick(r.line, e.target.checked)}
                          className="size-4 accent-hema"
                        />
                      </td>
                      <td className="px-2 py-1.5">
                        {s.name || "—"}
                        {s.companyName && s.companyName !== s.name && <span className="block text-meta text-ink-3">{s.companyName}</span>}
                      </td>
                      <td className="px-2 py-1.5 font-mono text-meta">{s.tin ? `${s.tin}-${s.branchCode ?? "00000"}` : "—"}</td>
                      <td className="px-2 py-1.5 text-meta text-ink-2">{[s.email, s.phone ?? s.mobile].filter(Boolean).join(" · ") || "—"}</td>
                      <td className="px-2 py-1.5 text-meta text-ink-2">{s.termsDays ? `${s.termsDays} days` : "On receipt"}</td>
                      <td className="py-1.5 pr-3 pl-2">
                        <span className={`rounded-full px-2 py-0.5 text-meta font-medium ${STATUS[r.status].tone}`}>{STATUS[r.status].label}</span>
                        {r.note && <span className="mt-0.5 block text-meta text-ink-2">{r.note}</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex gap-2">
            <Button variant="primary" loading={importing} disabled={!chosen.length} onClick={go}>
              Import {chosen.length} {chosen.length === 1 ? "supplier" : "suppliers"}
            </Button>
            <Button
              variant="quiet"
              onClick={() => {
                reset();
                setOpen(false);
              }}
            >
              Cancel
            </Button>
          </div>
        </>
      )}
      {!check && (
        <Button variant="quiet" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      )}
    </section>
  );
}
