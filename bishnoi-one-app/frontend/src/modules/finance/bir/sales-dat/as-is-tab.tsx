"use client";

import { useMemo, useState } from "react";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Field, Input } from "@/src/modules/finance/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { Drop } from "@/src/modules/finance/bir/sales-dat/drop";
import { csvName, saveText } from "@/src/modules/finance/bir/sales-dat/download";
import { Fold, Table, pl } from "@/src/modules/finance/bir/sales-dat/parts";
import { addressBook, buildDAT, checkDAT, clean, datToSalesReliefCSV, fmt, nameChanges, oneRowPerCustomer, parseCSV, parseOojeema, splitAddr, tin9, tinMap, validate, type Company } from "@/src/modules/finance/bir/sales-dat/index";

// "Convert as-is": one Sales Relief CSV into a DAT exactly as it is, no corrections
// (the converter's second tab: its fillSetup and run, followed line by line).

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;
type Header = { tin: string; name: string; trade: string; a1: string; a2: string; period: string; rdo: string; fy: string; rate: string };

export function AsIsTab({ companies }: { companies: Company[] }) {
  const [parsed, setParsed] = useState<Any>(null);
  const [csvFile, setCsvFile] = useState<string | null>(null);
  const [book, setBook] = useState<Any>(null);
  const [datFile, setDatFile] = useState<string | null>(null);
  const [h, setH] = useState<Header | null>(null);
  const [perCustomer, setPerCustomer] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* the header details, filled in from the CSV (and the DAT's own header, when one is added) */
  function fill(p: Any, b: Any) {
    const r = p.rows[0], company = companies.find((c) => c.tin === tin9(p.taxpayer.tin));
    let a1: string, a2: string;
    if (b && b.header) [a1, a2] = [b.header.a1, b.header.a2];
    else [a1, a2] = splitAddr(p.taxpayer.address);
    const day = new Date(r.year, r.month, 0).getDate();
    setH({
      tin: p.taxpayer.tin,
      /* clean(text, width): no width given, as the converter calls it */
      name: clean(p.taxpayer.name || p.taxpayer.tradeName, 0),
      trade: clean(p.taxpayer.tradeName || p.taxpayer.name, 0),
      a1, a2,
      period: `${String(r.month).padStart(2, "0")}/${String(day).padStart(2, "0")}/${r.year}`,
      rdo: (b && b.header && b.header.rdo) || company?.rdo || "",
      fy: String((b && b.header && b.header.fy) || company?.yearEndMonth || ""),
      rate: "12",
    });
  }

  async function addCsv(files: File[]) {
    setError(null);
    try {
      const p = parseOojeema(await files[0].text());
      if (!p.rows.length) throw new Error("No sales rows found. Is this the Sales Relief CSV export?");
      setParsed(p);
      setCsvFile(files[0].name);
      fill(p, book);
    } catch (e) {
      setError(`Could not read that CSV. ${(e as Error).message}`);
    }
  }
  async function addDat(files: File[]) {
    setError(null);
    try {
      const b = addressBook(await files[0].text());
      if (!Object.keys(b.byTin).length && !b.header) throw new Error("No H or D records found. Is this a RELIEF DAT file?");
      setBook(b);
      setDatFile(files[0].name);
      if (parsed) fill(parsed, b);
    } catch (e) {
      setError(`Could not read that DAT. ${(e as Error).message}`);
    }
  }

  const result: Any = useMemo(() => {
    if (!parsed || !h) return null;
    const p = JSON.parse(JSON.stringify(parsed));
    const merge = perCustomer ? oneRowPerCustomer(p.rows) : null;
    if (merge) p.rows = merge.rows;
    p.taxpayer.tin = h.tin;
    p.taxpayer.name = h.name;
    p.taxpayer.tradeName = h.trade;
    const rate = parseFloat(h.rate) || 12, per = h.period.trim(), m = per.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    try {
      const out: Any = buildDAT(p, { book, rdo: h.rdo.trim() || "53A", fyMonth: h.fy, day: m ? parseInt(m[2], 10) : null });
      if (m) {
        out.text = out.text.replace(/\d{2}\/\d{2}\/\d{4}/g, per);
        out.filename = tin9(p.taxpayer.tin) + "S" + m[1] + m[3] + ".DAT";
      }
      // the taxpayer's address, as typed
      const lines = out.text.split("\r\n");
      const head = parseCSV(lines[0] + "\n")[0];
      head[8] = clean(h.a1, 30);
      head[9] = clean(h.a2, 30);
      lines[0] = head.map((v: string, i: number) => ([2, 3, 4, 5, 6, 7, 8, 9, 14].indexOf(i) >= 0 ? '"' + v + '"' : v)).join(",");
      out.text = lines.join("\r\n");
      out.checks = checkDAT(out.text, out.filename, p.rows.length);
      return { out, merge, rows: p.rows, issues: validate(parsed, rate) as Any[] };
    } catch (e) {
      return { error: (e as Error).message };
    }
  }, [parsed, h, book, perCustomer]);

  const set = (k: keyof Header) => (e: { target: { value: string } }) => setH((x) => (x ? { ...x, [k]: e.target.value } : x));
  const out = result?.out ?? null;
  const issues: Any[] = result?.issues ?? [];
  const count = (s: string) => issues.filter((i) => i.sev === s).length;
  const blocked = !h || !h.rdo.trim() || !h.fy;
  const tins = parsed ? parsed.rows.map((r: Any) => r.tin).concat([parsed.taxpayer.tin]) : [];

  return (
    <div className="space-y-5">
      <p className="rounded-[3px] border-l-4 border-hema bg-sheet px-4 py-3 text-sm text-ink-2 shadow-sheet">
        Copies one Sales Relief CSV into a DAT <b>exactly as it is</b>, with no corrections. For filing, use <b>Prepare monthly DAT</b>, which applies the confirmed rules and checks the result against the Income Statement.
      </p>
      <Sheet className="space-y-3 px-5 py-4">
        <SectionTitle icon="lists">1. Sales Relief CSV</SectionTitle>
        <Drop title={csvFile || "Drop the CSV here, or choose it"} hint="Exported from Oojeema: Tax Reports → Sales Relief → CSV" accept=".csv,text/csv" multiple={false} onFiles={addCsv} />
        <Drop title={datFile || "Optional: add Oojeema's DAT for the same month"} hint="Reuses its exact address split" accept=".dat,.DAT,text/plain" multiple={false} onFiles={addDat} />
        {error && <p className="text-meta text-danger">{error}</p>}
      </Sheet>

      {h && result && (
        <Sheet>
          <div className="px-5 pt-4">
            <SectionTitle icon="approvals">2. Check and download</SectionTitle>
          </div>
          {result.error && <p className="px-5 pb-3 text-sm text-danger">The DAT could not be built. {result.error}</p>}
          {out && (
            <>
              <div className="grid grid-cols-2 divide-x divide-rule border-t border-rule sm:grid-cols-6">
                {[
                  ["Lines in the DAT", String(out.count)],
                  ["Exempt", fmt(Math.round(out.totals.exempt * 100))],
                  ["Zero-rated", fmt(Math.round(out.totals.zero * 100))],
                  ["VATable", fmt(Math.round(out.totals.taxable * 100))],
                  ["Output VAT", fmt(Math.round(out.totals.vat * 100))],
                  ["Rows without TIN", String(parsed.rows.filter((r: Any) => !tin9(r.tin)).length)],
                ].map(([k, v]) => (
                  <div key={k} className="min-w-0 px-5 py-3">
                    <span className="block text-meta text-ink-3">{k}</span>
                    <span className="block font-mono text-base font-semibold tabular-nums">{v}</span>
                  </div>
                ))}
              </div>
              <p className={`border-t border-rule px-5 py-3 text-sm ${count("error") ? "text-danger" : "text-ink-2"}`}>
                {count("error")
                  ? `${pl(count("error"), "row has a problem", "rows have problems")} that must be fixed before filing. Fix these in Oojeema first.`
                  : count("warn")
                    ? `${pl(count("warn"), "row needs", "rows need")} a look before filing.`
                    : "Nothing flagged."}
              </p>
              <div className="flex flex-wrap items-center gap-2 border-t border-rule px-5 py-4">
                <Button variant="primary" disabled={blocked} onClick={() => saveText(out.text, out.filename)}>Download DAT</Button>
                <Button disabled={blocked} onClick={() => saveText(datToSalesReliefCSV(out.text, tinMap(tins)).text, csvName(out.filename), "text/csv;charset=utf-8")}>Sales Relief (CSV)</Button>
                <Button onClick={() => navigator.clipboard.writeText(out.text)}>Copy text</Button>
                <span className="font-mono text-meta text-ink-3">{out.filename}</span>
              </div>
              {blocked && <p className="px-5 pb-4 text-meta text-danger">Fill in the RDO code and year-end month under Header details to download.</p>}
            </>
          )}
        </Sheet>
      )}

      {h && (
        <div className="space-y-2">
          {issues.length > 0 && (
            <Fold title="Rows flagged" note={[count("error") && `${count("error")} must fix`, count("warn") && `${count("warn")} to review`, count("info") && `${count("info")} notes`].filter(Boolean).join(" · ")}>
              <Table head={["Line", "Customer", "Check"]} rows={issues.slice(0, 400).map((i) => [String(i.line), String(i.name), `${i.sev === "error" ? "Must fix: " : i.sev === "warn" ? "Review: " : ""}${i.msg}`])} />
            </Fold>
          )}
          <Fold title="Header details" note="filled in from the CSV">
            <div className="grid gap-4 px-5 py-4 sm:grid-cols-3">
              <Field label="TIN">{(p) => <Input {...p} value={h.tin} onChange={set("tin")} />}</Field>
              <Field label="Registered name">{(p) => <Input {...p} value={h.name} onChange={set("name")} />}</Field>
              <Field label="Trade name">{(p) => <Input {...p} value={h.trade} onChange={set("trade")} />}</Field>
              <Field label="Address line 1" hint="Up to 30 characters">{(p) => <Input {...p} value={h.a1} maxLength={30} onChange={set("a1")} />}</Field>
              <Field label="Address line 2" hint="Up to 30 characters">{(p) => <Input {...p} value={h.a2} maxLength={30} onChange={set("a2")} />}</Field>
              <Field label="Period ending" hint="MM/DD/YYYY">{(p) => <Input {...p} value={h.period} onChange={set("period")} />}</Field>
              <Field label="RDO code" hint="The BIR office the company is registered at (Certificate of Registration, BIR Form 2303)">{(p) => <Input {...p} value={h.rdo} onChange={set("rdo")} />}</Field>
              <Field label="Year-end month" hint="1 to 12; 12 = December">{(p) => <Input {...p} type="number" min={1} max={12} value={h.fy} onChange={set("fy")} />}</Field>
              <Field label="VAT rate %" hint="Used only to check output VAT">{(p) => <Input {...p} type="number" value={h.rate} onChange={set("rate")} />}</Field>
            </div>
            <label className="flex items-start gap-2 px-5 pb-4 text-sm">
              <input type="checkbox" className="mt-1" checked={perCustomer} onChange={(e) => setPerCustomer(e.target.checked)} />
              <span>
                One line per customer
                <span className="block text-meta text-ink-3">All of a customer&apos;s invoices for the month are added into one line (by TIN; by name when there is no TIN).</span>
              </span>
            </label>
          </Fold>
          {out && result?.rows && (
            <Fold title="Customer names" note={`${nameChanges(result.rows).length} spelled differently in the DAT`}>
              <Table head={["Name in Oojeema", "Name in the DAT", "Why"]} rows={nameChanges(result.rows).map((x: Any) => [x.original, x.dat, x.check ? "Rules: worth checking" : "Rules"])} />
            </Fold>
          )}
          {out && (
            <Fold title="Preview and file checks">
              <pre className="overflow-x-auto bg-bench px-5 py-3 font-mono text-meta">{out.text.split("\r\n").slice(0, 6).join("\n")}{out.count > 5 ? `\n… ${out.count - 5} more detail rows` : ""}{!book ? "\n\nNo Oojeema DAT added: customer addresses were split automatically at a word boundary. Amounts and TINs are unaffected." : ""}</pre>
              <ul className="space-y-1 px-5 py-3 text-sm">
                {out.checks.map((c: Any) => (
                  <li key={c.label} className={c.ok ? "" : "text-danger"}>
                    <span className="inline-block w-5 font-mono">{c.ok ? "✓" : "✗"}</span>
                    {c.label}
                  </li>
                ))}
              </ul>
            </Fold>
          )}
        </div>
      )}
    </div>
  );
}
