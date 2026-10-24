"use client";

import { useState } from "react";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { Drop } from "@/src/modules/finance/bir/sales-dat/drop";
import { csvName, saveText } from "@/src/modules/finance/bir/sales-dat/download";
import { classify, datToSalesReliefCSV, fmt, parseCSV, parseSJ, parseSRGrid, readXlsx, tinMap } from "@/src/modules/finance/bir/sales-dat/index";

// "DAT to CSV": a sales DAT back into the Sales Relief layout, e.g. to check a filed DAT
// in Excel (the converter's third tab). A DAT keeps only 9 TIN digits; Oojeema's Sales
// Relief or Sales Journal, added alongside, fill in the full TIN with its branch code.

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;

export function DatCsvTab() {
  const [dat, setDat] = useState<{ text: string; name: string } | null>(null);
  const [tins, setTins] = useState<string[]>([]);
  const [from, setFrom] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function add(files: File[]) {
    setError(null);
    const found: string[] = [], names: string[] = [];
    let d: { text: string; name: string } | null = null;
    const takeGrid = (grid: Any, name: string) => {
      const k = classify(grid);
      if (!k) return;
      if (k.kind === "sr") {
        const p = parseSRGrid(grid, name);
        found.push(...p.rows.map((r: Any) => r.tin), p.taxpayer.tin);
        names.push(name);
      } else if (k.kind === "sj") {
        found.push(...parseSJ(grid, k.h, name).lines.map((l: Any) => l.tin));
        names.push(name);
      }
    };
    try {
      for (const file of files) {
        if (/\.xlsx$/i.test(file.name)) {
          (await readXlsx(await file.arrayBuffer())).forEach((s: Any) => takeGrid(s.grid, `${file.name} › ${s.name}`));
          continue;
        }
        const t = (await file.text()).replace(/^﻿/, "");
        if (/^H,S,/.test(t)) d = { text: t, name: file.name };
        else takeGrid(parseCSV(t), file.name);
      }
      if (d) setDat(d);
      setTins((x) => [...x, ...found]);
      setFrom((x) => [...x, ...names]);
    } catch (e) {
      setError(`Could not read one of the files. ${(e as Error).message}`);
    }
  }

  let out: Any = null, convertError: string | null = null;
  if (dat) {
    try {
      out = datToSalesReliefCSV(dat.text, tinMap(tins));
    } catch (e) {
      convertError = `Could not convert that DAT. ${(e as Error).message}`;
    }
  }

  return (
    <div className="space-y-5">
      <p className="rounded-[3px] border-l-4 border-hema bg-sheet px-4 py-3 text-sm text-ink-2 shadow-sheet">
        Turns a sales DAT back into a CSV in the Sales Relief layout, for example to check a filed DAT in Excel.
      </p>
      <Sheet className="space-y-3 px-5 py-4">
        <SectionTitle icon="lists">1. DAT file</SectionTitle>
        <Drop
          title={dat ? `${dat.name}${from.length ? " + " + from.join(", ") : ""}` : from.length ? "Now drop the DAT file itself" : "Drop a sales DAT here, or choose it"}
          hint="Optional: add Oojeema's Sales Relief CSV or Sales Journal at the same time. A DAT keeps only 9 TIN digits; those files fill in the full TIN with its branch code."
          accept=".dat,.DAT,.csv,.xlsx,.txt"
          onFiles={add}
        />
        {(error || convertError) && <p className="text-meta text-danger">{error || convertError}</p>}
      </Sheet>
      {out && dat && (
        <Sheet>
          <div className="px-5 pt-4">
            <SectionTitle icon="approvals">2. Download the CSV</SectionTitle>
          </div>
          <div className="grid grid-cols-2 divide-x divide-rule border-t border-rule sm:grid-cols-6">
            {[
              ["Rows", String(out.rows)],
              ["Exempt", fmt(out.totals.exempt)],
              ["Zero-rated", fmt(out.totals.zero)],
              ["VATable", fmt(out.totals.taxable)],
              ["Output VAT", fmt(out.totals.vat)],
              ["Full TINs", `${out.tinFull} of ${out.tinFull + out.tinShort}`],
            ].map(([k, v]) => (
              <div key={k} className="min-w-0 px-5 py-3">
                <span className="block text-meta text-ink-3">{k}</span>
                <span className="block font-mono text-base font-semibold tabular-nums">{v}</span>
              </div>
            ))}
          </div>
          <pre className="overflow-x-auto border-t border-rule bg-bench px-5 py-3 font-mono text-meta">{out.text.replace(/^﻿/, "").split("\n").slice(0, 17).join("\n")}{"\n…"}</pre>
          <div className="flex flex-wrap items-center gap-2 border-t border-rule px-5 py-4">
            <Button variant="primary" onClick={() => saveText(out.text, csvName(dat.name), "text/csv;charset=utf-8")}>Download CSV</Button>
            <span className="font-mono text-meta text-ink-3">{csvName(dat.name)}</span>
          </div>
          <p className="px-5 pb-4 text-meta text-ink-3">
            Same layout as Oojeema&apos;s Sales Relief CSV. Names, addresses and amounts are exactly as in the DAT.{" "}
            {out.tinShort
              ? `${out.tinShort} TIN${out.tinShort === 1 ? " is" : "s are"} written with 9 digits only (no branch code), because the DAT does not keep it${from.length ? " and the files added don't have it." : ": add Oojeema's Sales Relief CSV or Sales Journal to fill them in."}`
              : "All TINs include their branch code."}
          </p>
        </Sheet>
      )}
    </div>
  );
}
