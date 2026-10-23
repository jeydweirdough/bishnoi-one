"use client";

import { Upload } from "lucide-react";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { FormError } from "@/src/platform/ui/field";
import { checkImport, importAccounts } from "./actions";
import { chartRows } from "./csv";
import { TYPE_LABELS, type AccountType, type ImportCheck, type ImportRow } from "./types";

const STATUS: Record<ImportRow["status"], { label: string; tone: string }> = {
  new: { label: "New", tone: "bg-hema-tint text-hema" },
  here: { label: "Already here", tone: "bg-bench text-ink-2" },
  problem: { label: "Needs a look", tone: "bg-danger-tint text-danger" },
};

/**
 * Importing a chart of accounts from a CSV (Oojeema's or Zoho's export), decided 2026-10-23.
 * The file is read here in the browser; its rows are checked by the API and shown as they'd
 * be saved. New rows are ticked; a row Finance can't type gets a type picked here. Import adds
 * the ticked rows all or none. Existing accounts, entries and default accounts never change.
 */
export function ChartImport() {
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [fileName, setFileName] = useState("");
  const [check, setCheck] = useState<ImportCheck | null>(null);
  const [ticked, setTicked] = useState<Set<number>>(new Set());
  const [picked, setPicked] = useState<Record<number, AccountType>>({});
  const [error, setError] = useState<string | null>(null);
  const [reading, read] = useTransition();
  const [importing, run] = useTransition();

  const typeOf = (r: ImportRow) => picked[r.line] ?? r.type;
  // Only a missing type can be put right here; a code or name problem is fixed in the file.
  const importable = (r: ImportRow) => r.status !== "here" && r.problems.every((p) => p === "type") && !!typeOf(r);
  const chosen = check ? check.rows.filter((r) => ticked.has(r.line) && importable(r)) : [];

  function reset() {
    setCheck(null);
    setTicked(new Set());
    setPicked({});
    setError(null);
    setFileName("");
    if (input.current) input.current.value = "";
  }

  function choose(file: File | undefined) {
    if (!file) return;
    read(async () => {
      reset();
      setFileName(file.name);
      const rows = chartRows(await file.text());
      if (!rows) return setError("This file has no Code and Name columns. Export the chart of accounts as CSV with its headings (Code, Name, Class…).");
      if (!rows.length) return setError("The file has headings but no accounts.");
      if (rows.length > 3000) return setError("The file has over 3,000 rows: split it, and import each part.");
      const result = await checkImport(rows);
      if (!result.ok) return setError(result.error);
      setCheck(result.data);
      setTicked(new Set(result.data.rows.filter((r) => r.status === "new").map((r) => r.line)));
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
      const result = await importAccounts(
        chosen.map((r) => ({ code: r.code, name: r.name, type: typeOf(r) as AccountType, description: r.description ?? r.kind, parent: r.parent })),
      );
      if (!result.ok) return setError(result.error);
      toast.success(`${result.data.added} accounts imported`, {
        description: result.data.withParent ? `${result.data.withParent} placed under their parent account.` : undefined,
      });
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
        <p className="text-sm font-semibold">Import a chart of accounts</p>
        <p className="text-meta text-ink-2">
          A CSV with headings: Oojeema&apos;s (Code, Name, Class, Nature, Parent…) or Zoho&apos;s (Account Code, Account Name, Account Type…). The file is read
          here and not kept. Nothing is added until you press Import, and accounts already here are left as they are.
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
            <table className="w-full min-w-[56rem] text-sm">
              <thead className="sticky top-0 bg-sheet">
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th className="w-10 py-2 pl-3">
                    <input
                      type="checkbox"
                      aria-label="Tick every row that can be imported"
                      checked={chosen.length > 0 && chosen.length === check.rows.filter(importable).length}
                      onChange={(e) => setTicked(new Set(e.target.checked ? check.rows.filter(importable).map((r) => r.line) : []))}
                      className="size-4 accent-hema"
                    />
                  </th>
                  <th className="w-28 px-2 py-2 font-semibold">Code</th>
                  <th className="px-2 py-2 font-semibold">Name</th>
                  <th className="w-36 px-2 py-2 font-semibold">Type</th>
                  <th className="px-2 py-2 font-semibold">Parent</th>
                  <th className="w-64 py-2 pr-3 pl-2 font-semibold">What happens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {check.rows.map((r) => {
                  const can = importable(r);
                  const needsType = r.status !== "here" && r.problems.includes("type");
                  return (
                    <tr key={r.line} className={`align-top ${r.status === "here" ? "text-ink-3" : ""}`}>
                      <td className="py-1.5 pl-3">
                        <input
                          type="checkbox"
                          aria-label={`Import line ${r.line}: ${r.code} ${r.name}`}
                          disabled={!can}
                          checked={can && ticked.has(r.line)}
                          onChange={(e) => tick(r.line, e.target.checked)}
                          className="size-4 accent-hema"
                        />
                      </td>
                      <td className="px-2 py-1.5 font-mono text-meta">{r.code || "—"}</td>
                      <td className="px-2 py-1.5">
                        {r.name || "—"}
                        {r.kind && <span className="block text-meta text-ink-3">{r.kind}</span>}
                      </td>
                      <td className="px-2 py-1.5">
                        {needsType ? (
                          <select
                            aria-label={`Line ${r.line}: type`}
                            value={picked[r.line] ?? ""}
                            onChange={(e) => {
                              setPicked({ ...picked, [r.line]: e.target.value as AccountType });
                              if (e.target.value) tick(r.line, true);
                            }}
                            className="h-8 w-full rounded-[3px] border border-danger bg-sheet px-2 text-sm"
                          >
                            <option value="">Pick a type…</option>
                            {(Object.keys(TYPE_LABELS) as AccountType[]).map((t) => (
                              <option key={t} value={t}>
                                {TYPE_LABELS[t]}
                              </option>
                            ))}
                          </select>
                        ) : r.type ? (
                          TYPE_LABELS[r.type]
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-2 py-1.5 text-meta text-ink-2">
                        {r.parent ?? "—"}
                        {r.parent && r.parentFound && <span className="block text-ink-3">{r.parentFound === "file" ? "in this file" : "already in the chart"}</span>}
                      </td>
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
              Import {chosen.length} {chosen.length === 1 ? "account" : "accounts"}
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
