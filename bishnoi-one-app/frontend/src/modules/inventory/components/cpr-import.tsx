"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/inventory/platform/ui/button";
import { FileDrop } from "@/src/modules/inventory/platform/ui/file-drop";
import { Textarea } from "@/src/modules/inventory/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { importCpr, type CprCheck, type CprLine } from "@/src/modules/inventory/actions/inventory";
import { Table, Td } from "@/src/modules/inventory/components/ui";

/** One line of a CSV file or of cells pasted from a spreadsheet (tab-separated), quotes kept together. */
function cells(line: string, sep: string): string[] {
  const out: string[] = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cur += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === sep) { out.push(cur.trim()); cur = ""; }
    else cur += ch;
  }
  out.push(cur.trim());
  return out;
}

/** SKU, CPR number and valid until, found by their headings (or in that order when there are none). */
function readRows(text: string): CprLine[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  if (!lines.length) return [];
  const sep = lines[0].includes("\t") ? "\t" : ",";
  const head = cells(lines[0], sep).map((h) => h.toLowerCase());
  const at = (...names: string[]) => head.findIndex((h) => names.some((n) => h.includes(n)));
  const sku = at("sku", "code"), number = at("cpr", "registration"), until = at("valid", "expir", "until");
  const headed = sku >= 0 && number >= 0;
  const [a, b, c] = headed ? [sku, number, until] : [0, 1, 2];
  return (headed ? lines.slice(1) : lines).map((l) => {
    const r = cells(l, sep);
    return { sku: r[a] ?? "", cprNumber: r[b] || null, validUntil: c >= 0 ? r[c] || null : null };
  });
}

const RESULT = { change: "Will change", same: "No change", problem: "Problem" } as const;

/** Many products' CPR numbers at once: read, checked by the API, then saved. */
export function CprImport() {
  const [text, setText] = useState("");
  const [check, setCheck] = useState<CprCheck | null>(null);
  const [rows, setRows] = useState<CprLine[]>([]);
  const [pending, start] = useTransition();

  function run(apply: boolean, lines = rows) {
    if (!lines.length) return toast.error("Add at least one row: SKU, CPR number, valid until.");
    start(async () => {
      const r = await importCpr(lines, apply);
      if (!r.ok) return void toast.error(r.error);
      setCheck(r.data);
      if (apply) toast.success(`${r.data.saved} product${r.data.saved === 1 ? "" : "s"} updated`);
    });
  }

  function read(from: string) {
    const lines = readRows(from);
    setRows(lines);
    setCheck(null);
    run(false, lines);
  }

  return (
    <div className="space-y-5">
      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <SectionTitle icon="letters">Rows to update</SectionTitle>
        <p className="mt-1 text-meta text-ink-3">
          Three columns: SKU, CPR number, Valid until (2027-03-31 or 31/03/2027). Upload a CSV file, or copy the cells from a spreadsheet and paste them below. A blank date keeps the one already kept.
        </p>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <FileDrop accept=".csv,.txt" note="CSV, up to 1 MB" maxBytes={1024 * 1024} onFile={async (f) => f && read(await f.text())} busy={pending} aria-label="CSV file of CPR numbers" />
          <div className="space-y-2">
            <Textarea aria-label="Pasted rows" rows={5} value={text} placeholder={"SKU\tCPR number\tValid until\nPCM-500\tDR-XY12345\t31/03/2027"} onChange={(e) => setText(e.target.value)} className="font-mono text-meta" />
            <Button size="sm" onClick={() => read(text)} loading={pending && !check}>Check pasted rows</Button>
          </div>
        </div>
      </Sheet>

      {check && (
        <Sheet>
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 sm:px-6">
            <p className="text-sm text-ink-2">
              {check.saved ? <strong className="text-ink">{check.saved} saved. </strong> : null}
              {check.changes} to change, {check.same} unchanged, {check.problems} with a problem{check.problems ? ": fix them in the file and check again, or save the rest" : ""}.
            </p>
            {check.changes > 0 && !check.saved && (
              <Button variant="primary" onClick={() => run(true)} loading={pending}>
                Save {check.changes} change{check.changes === 1 ? "" : "s"}
              </Button>
            )}
          </div>
          <Table head={["Line", "SKU", "Product", "CPR number", "Valid until", "Result"]} min="44rem">
            {check.rows.map((r) => (
              <tr key={r.line} className={r.result === "problem" ? "bg-danger/5" : ""}>
                <Td>{r.line}</Td>
                <Td><span className="font-mono">{r.sku}</span></Td>
                <Td>{r.product?.name ?? "—"}</Td>
                <Td><span className="font-mono">{r.cprNumber ?? "—"}</span></Td>
                <Td>{r.validUntil ?? "—"}</Td>
                <Td>
                  <span className={r.result === "problem" ? "text-danger" : r.result === "change" ? "font-medium text-ink" : "text-ink-3"}>{RESULT[r.result]}</span>
                  {r.problems.length > 0 && <span className="block text-meta text-danger">{r.problems.join(" ")}</span>}
                  {r.changes.length > 0 && <span className="block text-meta text-ink-3">{r.changes.join(" and ")}</span>}
                </Td>
              </tr>
            ))}
          </Table>
        </Sheet>
      )}
    </div>
  );
}
