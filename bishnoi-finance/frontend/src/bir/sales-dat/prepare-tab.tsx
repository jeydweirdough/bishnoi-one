"use client";

import { useMemo, useState, type ReactNode } from "react";
import { Button } from "@/src/platform/ui/button";
import { Field, Input, Select } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { Drop } from "./drop";
import { csvName, saveBlob, saveText } from "./download";
import { Fold, Table, pl } from "./parts";
import {
  ADJ_CLASS, C, CONFIRMED_BY, OTHERWISE, ROLE_LABEL, RULES, buildXlsx, datToSalesReliefCSV, defaultMonth, emptyLoaded, explainGap, fmt,
  glCovers, monthLabel, monthName, months, nameChanges, prepareMonth, readFiles, reconSheets, statusOf, tin9, tinMap, tinsFor, withDefaultRoles, zipStore,
  type Company, type Loaded, type Role,
} from "./index";

// "Prepare monthly DAT": the converter's main tab (converter.html, "PREPARE MONTHLY DAT"),
// in Finance's look. The results come from prepare.ts and are the converter's own.

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;

export function PrepareTab({ companies }: { companies: Company[] }) {
  const [L, setL] = useState<Loaded>(emptyLoaded);
  const [month, setMonth] = useState<number | null>(null);
  const [roles, setRoles] = useState<Record<string, Role>>({});
  const [perCustomer, setPerCustomer] = useState(true);
  const [rdoInput, setRdoInput] = useState<string | null>(null);
  const [fyInput, setFyInput] = useState<string | null>(null);
  const [irInput, setIrInput] = useState("");
  const [adjClass, setAdjClass] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function add(files: File[]) {
    setBusy(true);
    setError(null);
    try {
      const next = await readFiles(files, L);
      setL(next);
      setRoles((r) => withDefaultRoles(next, r));
      setMonth((m) => defaultMonth(next, m));
    } catch (e) {
      setError(`Could not read one of the files. ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }
  function clearAll() {
    setL(emptyLoaded());
    setRoles({});
    setMonth(null);
    setRdoInput(null);
    setFyInput(null);
    setIrInput("");
    setAdjClass({});
  }

  /* Which company the files are for: the seller TIN in this month's Sales Relief (or Oojeema's DAT). */
  const sellerTin: string | null = (month != null && L.srAll[month]?.list?.taxpayer?.tin) || L.dat?.taxpayer?.tin || null;
  const company = sellerTin ? companies.find((c) => c.tin === tin9(sellerTin)) || null : null;
  /* An Oojeema DAT's own header wins over the company's settings, as in the converter; anything typed here wins over both. */
  const rdo = rdoInput ?? (L.dat?.header?.rdo || company?.rdo || "");
  const fy = fyInput ?? String(L.dat?.header?.fy || company?.yearEndMonth || "");
  const settingsMissing = !rdo.trim() || !fy;
  const typedIr = irInput.trim() ? C(irInput.trim()) : null;

  const options = useMemo(() => ({ roles, rdo, fyMonth: fy, perCustomer, adjClass }), [roles, rdo, fy, perCustomer, adjClass]);
  const o: Any = useMemo(() => (month != null ? prepareMonth(L, month, { ...options, typedIr }) : null), [L, month, options, typedIr]);
  const statuses = useMemo(() => Object.fromEntries(months(L).map((k) => [k, statusOf(prepareMonth(L, k, options))])), [L, options]);
  const gap = useMemo(() => (o ? explainGap(o) : {}), [o]);

  const ks = months(L);
  const anything = ks.length > 0 || !!L.gl || !!L.is || !!L.dat;
  const out = o?.fixOut;
  const canDownload = !!out && !settingsMissing;

  function downloadZip() {
    const files: { name: string; data: string }[] = [], warn: string[] = [];
    ks.forEach((k) => {
      const m = prepareMonth(L, k, options);
      if (!m.fixOut) return;
      if (!m.ready) warn.push(monthLabel(k));
      files.push({ name: m.fixOut.filename, data: m.fixOut.text });
      files.push({ name: csvName(m.fixOut.filename), data: datToSalesReliefCSV(m.fixOut.text, tinMap(tinsFor(m))).text });
    });
    if (!files.length) return;
    if (warn.length && !confirm(`${warn.join(", ")} ${warn.length === 1 ? "needs" : "need"} checking before filing (see the month buttons).\n\nDownload all months anyway?`)) return;
    saveBlob(new Blob([zipStore(files)], { type: "application/zip" }), `BIR Sales DAT ${monthLabel(ks[0])}${ks.length > 1 ? " to " + monthLabel(ks[ks.length - 1]) : ""}.zip`);
  }

  return (
    <div className="space-y-5">
      {/* 1. The files */}
      <Sheet className="px-5 py-4">
        <SectionTitle icon="lists">1. Add Oojeema&apos;s exports</SectionTitle>
        <Drop
          title={anything ? "Add more files" : "Drop the files here, or choose them"}
          hint="Sales Journal, Sales Relief, General Ledgers and the Income Statement Monthly, as CSV or Excel. Add several months at once to prepare them together. Nothing is uploaded: the files are read on this computer."
          accept=".xlsx,.csv,.dat,.DAT,.txt"
          onFiles={add}
        />
        {busy && <p className="mt-2 text-meta text-ink-3">Reading…</p>}
        {error && <p className="mt-2 text-meta text-danger">{error}</p>}
        {anything && <LoadedFiles L={L} month={month} roles={roles} onClear={clearAll} />}
      </Sheet>

      {/* 2. The company, and the month */}
      {ks.length > 0 && (
        <Sheet className="px-5 py-4">
          <SectionTitle icon="company">2. Company and month</SectionTitle>
          <CompanySettings
            company={company}
            sellerTin={sellerTin}
            rdo={rdo}
            fy={fy}
            fromDat={!!L.dat?.header}
            onRdo={setRdoInput}
            onFy={setFyInput}
          />
          <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Month">
            {ks.map((k) => (
              <MonthButton key={k} k={k} status={statuses[k]} current={k === month} onClick={() => (setMonth(k), setIrInput(""))} />
            ))}
            {ks.length > 1 && (
              <Button size="sm" onClick={downloadZip} disabled={settingsMissing} className="self-center">
                Download all months (.zip)
              </Button>
            )}
          </div>
        </Sheet>
      )}

      {/* 3. Review and download */}
      {o && o.cor && (
        <>
          <Sheet>
            <div className="px-5 pt-4">
              <SectionTitle icon="approvals">3. {monthName(month)}: review and download</SectionTitle>
            </div>
            <Verdict o={o} L={L} roles={roles} month={month!} />
            <Stats o={o} />
            <div className="flex flex-wrap items-center gap-2 border-t border-rule px-5 py-4">
              <Button variant="primary" disabled={!canDownload} onClick={() => saveText(out.text, out.filename)}>
                Download DAT
              </Button>
              <Button disabled={!canDownload} onClick={() => saveText(datToSalesReliefCSV(out.text, tinMap(tinsFor(o))).text, csvName(out.filename), "text/csv;charset=utf-8")}>
                Sales Relief (CSV)
              </Button>
              <Button
                onClick={() =>
                  saveBlob(
                    new Blob([buildXlsx(reconSheets(o.res, { issues: o.issues, cor: o.cor, fixOut: o.fixOut }))], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
                    `Sales reconciliation ${Math.floor(month! / 100)}-${String(month! % 100).padStart(2, "0")}.xlsx`,
                  )
                }
              >
                Excel report
              </Button>
              {out && <span className="font-mono text-meta text-ink-3">{out.filename}</span>}
            </div>
            <p className="px-5 pb-4 text-meta text-ink-3">
              {settingsMissing
                ? "Fill in the RDO code and year-end month above to download the DAT."
                : out
                  ? `Submit it named exactly ${out.filename}. If your browser adds " (1)" to the name, rename it. Run it through the BIR RELIEF Validation Module before submitting.`
                  : ""}
            </p>
          </Sheet>

          <Attention o={o} gap={gap} adjClass={adjClass} onAdj={(id, v) => setAdjClass((a) => ({ ...a, [id]: v }))} />

          <div className="space-y-2">
            <Fold title="What was changed" note={changedNote(o)}>
              <ChangeLog o={o} />
            </Fold>
            <Fold title={`Lines in the DAT${out ? ` (${out.rows.length})` : ""}`} note="click a customer to see its invoices">
              {out && <DatLines rows={out.rows} />}
            </Fold>
            <Fold title="Customer names" note={namesNote(o.cor.rows)}>
              <Names rows={o.cor.rows} />
            </Fold>
            <Fold title="File checks" note={out ? (out.checks.some((c: Any) => !c.ok) ? `${out.checks.filter((c: Any) => !c.ok).length} failed` : `all ${out.checks.length} passed`) : ""}>
              {out && <Checks checks={out.checks} />}
            </Fold>
            <Fold title="Settings" note={`${perCustomer ? "one line per customer" : "one line per invoice"} · RDO ${rdo || "—"} · year ends ${MONTH_NAMES[(parseInt(fy, 10) || 12) - 1]}`}>
              <div className="space-y-4 px-5 py-4 text-sm">
                <label className="flex items-start gap-2">
                  <input type="checkbox" className="mt-1" checked={perCustomer} onChange={(e) => setPerCustomer(e.target.checked)} />
                  <span>
                    One line per customer
                    <span className="block text-meta text-ink-3">All of a customer&apos;s invoices for the month are added into one line (by TIN; by name when there is no TIN). Untick for one line per invoice.</span>
                  </span>
                </label>
                <Field label="IR (sales per the Income Statement)" hint={irInput ? "Typed by hand. Clear it to use the Income Statement again." : o.irNote || "Add the Income Statement Monthly, or type the figure."} className="max-w-xs">
                  {(p) => <Input {...p} value={irInput} placeholder={o.irC != null && !irInput ? fmt(o.irC) : "from the Income Statement"} onChange={(e) => setIrInput(e.target.value)} className="font-mono" />}
                </Field>
                <GlRoles L={L} roles={roles} onChange={(n, r) => setRoles((x) => ({ ...x, [n]: r }))} />
              </div>
            </Fold>
            <Fold title="Rules in use" note={`confirmed by ${CONFIRMED_BY}, October 2026`}>
              <RulesList />
            </Fold>
          </div>
        </>
      )}
      {o && !o.cor && o.sj && <p className="text-sm text-ink-2">Add the {monthName(month)} Sales Relief: the DAT is built from it.</p>}
    </div>
  );
}

/* --- step 1: what's loaded --- */
function LoadedFiles({ L, month, roles, onClear }: { L: Loaded; month: number | null; roles: Record<string, Role>; onClear: () => void }) {
  const list = (all: Record<number, unknown>) => Object.keys(all).map(Number).sort((a, b) => a - b).map(monthLabel).join(", ") || "Not added";
  const period = (p: Any) => (p.a === p.b ? monthLabel(p.a) : `${monthLabel(p.a)} – ${monthLabel(p.b)}`);
  const ml = month ? monthName(month) : "the month";
  const glAccounts = L.gl ? Object.keys(L.gl.accounts) : [];
  const missing = [month != null && !L.sjAll[month] && "Sales Journal", month != null && !L.srAll[month] && "Sales Relief"].filter(Boolean);
  const salesGl = month != null && glAccounts.some((n) => roles[n] === "sales" && glCovers(L, n, month));
  const rows: [string, ReactNode][] = [
    ["Sales Journal", list(L.sjAll)],
    ["Sales Relief", list(L.srAll)],
    ["General Ledgers", glAccounts.length ? glAccounts.map((n) => `${n.replace(/\s*\([^)]*\)\s*$/, "")} (${L.gl.accounts[n].periods ? L.gl.accounts[n].periods.map(period).join(", ") : "all dates"})`).join(" · ") : "Not added"],
    ["Income Statement", L.is ? `${L.is.from}${L.is.year ? ` · ${L.is.year}` : ""}` : "Not added"],
    ["Oojeema DAT", L.dat ? L.dat.from : "Not added (optional: reuses Oojeema's address split)"],
  ];
  return (
    <div className="mt-4 text-sm">
      <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-[auto_1fr]">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-2">{k}</dt>
            <dd className="min-w-0 break-words">{v}</dd>
          </div>
        ))}
      </dl>
      {missing.length > 0 && <p className="mt-2 text-meta text-danger">Missing for {ml}: {missing.join(", ")}.</p>}
      {month != null && !missing.length && !salesGl && <p className="mt-2 text-meta text-ink-3">Recommended for {ml}: the Sale of Goods GL (finds journal entries posted straight to sales), the Deferred Sales GL, and the Income Statement.</p>}
      {L.notes.length > 0 && <p className="mt-2 text-meta text-danger">{L.notes.join(" · ")}</p>}
      <Button size="sm" className="mt-3" onClick={onClear}>Clear all</Button>
    </div>
  );
}

/* --- step 2: the company's details for the file, explained --- */
function CompanySettings({ company, sellerTin, rdo, fy, fromDat, onRdo, onFy }: {
  company: Company | null; sellerTin: string | null; rdo: string; fy: string; fromDat: boolean; onRdo: (v: string) => void; onFy: (v: string) => void;
}) {
  const known = !!company;
  return (
    <div className="space-y-3 text-sm">
      <p>
        {known ? <b>{company!.name}</b> : <b className="text-danger">A company Finance has no details for</b>}
        {sellerTin && <span className="text-ink-3"> · seller TIN {sellerTin}</span>}
      </p>
      <div className="grid max-w-xl gap-4 sm:grid-cols-2">
        <Field label="RDO code" hint="The BIR office the company is registered at, as on its Certificate of Registration (BIR Form 2303).">
          {(p) => <Input {...p} value={rdo} onChange={(e) => onRdo(e.target.value)} className="font-mono" placeholder="e.g. 53A" />}
        </Field>
        <Field label="Year-end month" hint="The month the company's accounting year ends. Most use December (a January–December year).">
          {(p) => (
            <Select {...p} value={fy} onChange={(e) => onFy(e.target.value)}>
              <option value="">Choose…</option>
              {MONTH_NAMES.map((m, i) => (
                <option key={m} value={String(i + 1)}>{m}</option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <p className="text-meta text-ink-3">
        {fromDat
          ? "Taken from the Oojeema DAT you added; change them only if they're wrong."
          : known
            ? company!.confirmed
              ? "Confirmed against the company's papers."
              : `Not yet confirmed: ${company!.note}`
            : "Fill these in before downloading. Both are on the first line of the DAT, and the BIR uses them to route the file to the company's office."}
      </p>
    </div>
  );
}

function MonthButton({ k, status, current, onClick }: { k: number; status?: Any; current: boolean; onClick: () => void }) {
  let text = "", tone = "text-ink-3";
  if (!status) text = "";
  else if (status.noSj) text = "No Sales Journal";
  else if (status.noList) text = "No Sales Relief";
  else if (status.err) [text, tone] = ["Could not build", "text-danger"];
  else if (status.ready) [text, tone] = ["✓ Matches the IR", "text-hema"];
  else if (status.noIr && !status.items) text = "Ready · no IR to check";
  else [text, tone] = [`! ${status.diff ? "Off by " + fmt(status.diff) : pl(status.items, "item") + " to check"}`, "text-danger"];
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={current}
      className={`flex min-w-36 flex-col items-start rounded-[3px] border px-3 py-2 text-left ${current ? "border-hema bg-hema-tint" : "border-rule-strong bg-sheet hover:border-control"}`}
    >
      <span className="text-sm font-semibold">{monthName(k)}</span>
      <span className={`text-meta ${tone}`}>{text}</span>
    </button>
  );
}

/* --- step 3 --- */
function Verdict({ o, L, roles, month }: { o: Any; L: Loaded; roles: Record<string, Role>; month: number }) {
  const out = o.fixOut;
  let tone = "text-ink", title = "", text = "";
  if (!out) [tone, title, text] = ["text-danger", "The DAT could not be built", o.err || ""];
  else if (o.ready) [tone, title, text] = ["text-hema", "Ready to file", "Matches the Income Statement (IR), and every difference from Oojeema's Sales Relief is covered by a confirmed rule. Run it through the BIR validation module, then submit."];
  else if (o.irC == null && !o.items) [title, text] = ["Built, not checked against the IR", "Every difference from the Sales Relief is covered by a confirmed rule, but there is no Income Statement to compare with. Add the Income Statement Monthly, or type the IR under Settings."];
  else
    [tone, title, text] = [
      "text-danger",
      "Check before filing",
      [o.diff ? `The DAT is ${fmt(Math.abs(o.diff))} ${o.diff > 0 ? "above" : "below"} the IR.` : "", o.items ? `${pl(o.items, "item is", "items are")} left as reported because no confirmed rule covers ${o.items === 1 ? "it" : "them"}.` : ""]
        .filter(Boolean)
        .join(" ") + " Details below.",
    ];
  const salesGl = Object.keys(roles).some((n) => roles[n] === "sales" && L.gl && L.gl.accounts[n] && glCovers(L, n, month));
  return (
    <div className="px-5 py-3">
      <p className={`text-base font-semibold ${tone}`}>{title}</p>
      <p className="mt-1 max-w-3xl text-sm text-ink-2">{text}</p>
      {out && !salesGl && <p className="mt-1 text-meta text-ink-3">Not checked for journal entries posted straight to sales: add the Sale of Goods GL for {monthName(month)} to include that check.</p>}
    </div>
  );
}

function Stats({ o }: { o: Any }) {
  const out = o.fixOut, cor = o.cor;
  const stats: [string, string, string?][] = [
    ["Lines in the DAT", out ? String(out.count) : "—", out && out.merge ? `one per customer, from ${pl(cor.rows.length, "row")}` : "one per row"],
    ["Net sales", fmt(cor.totals.net), "exempt + zero-rated + VATable"],
    ["Output VAT", fmt(cor.totals.vat)],
    ["IR", o.irC != null ? fmt(o.irC) : "—", o.irC != null ? (o.irTyped ? "typed by hand" : "from the Income Statement") : "no Income Statement"],
    ["Difference", o.diff == null ? "—" : o.diff === 0 ? "0.00 ✓" : fmt(o.diff), o.diff == null ? "" : o.diff === 0 ? "matches the IR" : "DAT − IR"],
  ];
  return (
    <div className="grid grid-cols-2 divide-x divide-rule border-t border-rule sm:grid-cols-5">
      {stats.map(([k, v, s]) => (
        <div key={k} className="min-w-0 px-5 py-3">
          <span className="block text-meta text-ink-3">{k}</span>
          <span className={`block font-mono text-base font-semibold tabular-nums ${k === "Difference" && o.diff ? "text-danger" : ""}`}>{v}</span>
          {s && <span className="block text-meta text-ink-3">{s}</span>}
        </div>
      ))}
    </div>
  );
}

function Attention({ o, gap, adjClass, onAdj }: { o: Any; gap: Any; adjClass: Record<string, string>; onAdj: (id: string, v: string) => void }) {
  const cor = o.cor, items = [...cor.pending.map((p: Any) => ["pending", p]), ...cor.open.map((p: Any) => ["open", p])];
  const adj = cor.adjustments || [];
  const sourceChecks = o.issues.filter((i: Any) => i.report !== "Income Statement");
  return (
    <div className="space-y-3">
      {o.diff ? (
        <Sheet className="px-5 py-4 text-sm">
          <p className="font-semibold">The DAT is {fmt(Math.abs(o.diff))} {o.diff > 0 ? "above" : "below"} the IR</p>
          {gap.parts ? (
            <>
              <p className="mt-1 text-ink-2">The difference is explained by:</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-ink-2">
                {gap.parts.map((p: Any) => (
                  <li key={p.t}>
                    {p.t.charAt(0).toUpperCase() + p.t.slice(1)} <b className="font-mono">({fmt(p.v)})</b>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="mt-1 text-ink-2">The loaded files don&apos;t explain it. The Excel report shows where the totals part.</p>
          )}
        </Sheet>
      ) : null}
      {items.length > 0 && (
        <Sheet className="text-sm">
          <div className="px-5 pt-4">
            <p className="font-semibold">{pl(items.length, "item")} left as reported</p>
            <p className="mt-1 text-ink-2">No confirmed rule covers {items.length === 1 ? "it" : "these"}, so the DAT shows {items.length === 1 ? "it" : "them"} exactly as Oojeema reports. Decide whether that is right before filing.</p>
          </div>
          <Table head={["Invoice", "Customer", "What to look at"]} rows={items.map(([kind, p]: Any) => [p.si || "—", p.name || "", (kind === "pending" ? "Decision pending: " : "") + p.msg])} />
        </Sheet>
      )}
      {adj.length > 0 && (
        <Sheet className="text-sm">
          <div className="px-5 pt-4">
            <p className="font-semibold">{pl(adj.length, "sales adjustment JV")}: confirm how {adj.length === 1 ? "it is" : "each is"} reported</p>
            <p className="mt-1 text-ink-2">A JV on Sale of Goods that names an invoice is added under that invoice&apos;s customer. It is reported as VATable with 12% output VAT unless you choose otherwise.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="mt-2 w-full text-sm">
              <thead>
                <tr className="text-left text-meta text-ink-3">
                  {["Voucher", "Invoice", "Customer", "Amount", "Report as", "Output VAT", "Description"].map((h) => (
                    <th key={h} className="px-5 py-1 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {adj.map((a: Any) => (
                  <tr key={a.id} className="border-t border-rule align-top">
                    <td className="px-5 py-1.5 font-mono">{a.voucher}<span className="block text-meta text-ink-3">{a.date}</span></td>
                    <td className="px-5 py-1.5 font-mono">{a.si}</td>
                    <td className="px-5 py-1.5">{a.name}</td>
                    <td className="px-5 py-1.5 text-right font-mono tabular-nums">{fmt(a.amt)}</td>
                    <td className="px-5 py-1.5">
                      <Select aria-label={`Report ${a.voucher} as`} value={adjClass[a.id] || a.cls} onChange={(e) => onAdj(a.id, e.target.value)}>
                        {Object.keys(ADJ_CLASS).map((k) => (
                          <option key={k} value={k}>
                            {(ADJ_CLASS as Record<string, string>)[k].replace(/ sales$/, "")}{k === "vatable" && !a.chosen ? " (default)" : ""}
                          </option>
                        ))}
                      </Select>
                    </td>
                    <td className="px-5 py-1.5 text-right font-mono tabular-nums">{fmt(a.vat)}</td>
                    <td className="px-5 py-1.5 text-meta text-ink-2">{a.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Sheet>
      )}
      {sourceChecks.length > 0 && (
        <Fold title={`${pl(sourceChecks.length, "source check")} flagged`} note="problems found in the files themselves (totals, TINs, GL balances)">
          <Table head={["Report", "Where", "Name", "Check"]} rows={sourceChecks.map((i: Any) => [i.report, i.where, i.name || "", i.msg])} />
        </Fold>
      )}
    </div>
  );
}

function changedNote(o: Any): string {
  const cor = o.cor, changed = cor.log.filter((e: Any) => e.changed && e.after != null && !e.added).length;
  return [cor.removed ? `${pl(cor.removed, "row")} left out` : "", cor.added ? `${cor.added} added` : "", changed ? `${pl(changed, "amount")} changed` : ""].filter(Boolean).join(" · ") || "nothing needed changing";
}

function ChangeLog({ o }: { o: Any }) {
  const rank = (e: Any) => (e.changed ? (e.added ? 0 : e.after == null ? 2 : 1) : 3);
  const log = [...o.cor.log].sort((a, b) => rank(a) - rank(b));
  if (!log.length) return <p className="px-5 py-3 text-sm text-ink-2">Nothing needed changing.</p>;
  return (
    <Table
      head={["Invoice", "Customer", "Rule", "Column", "Before", "After", "Basis / source"]}
      numeric={[4, 5]}
      rows={log.map((e: Any) => [
        e.si, e.name, e.rule + (e.changed ? "" : " (already so)"), e.column,
        e.before == null ? (e.added ? "added" : "—") : fmt(e.before), e.after == null ? "left out" : fmt(e.after),
        `${e.basis} · ${String(e.where).replace(/^.* (row|line) /, "$1 ")} · Sales Journal row ${e.sjRow}`,
      ])}
    />
  );
}

function DatLines({ rows }: { rows: Any[] }) {
  const [find, setFind] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const q = find.trim().toLowerCase(), digits = q.replace(/\D/g, "");
  const key = (r: Any) => tin9(r.tin) || "N" + r.name;
  const shown = rows.filter((r) => !q || r.name.toLowerCase().includes(q) || (digits && String(r.tin || "").replace(/\D/g, "").includes(digits)) || (r.parts || []).some((p: Any) => p.inv && String(p.inv.si).toLowerCase().includes(q)));
  const peso = (v: number) => fmt(Math.round(v * 100));
  return (
    <div>
      <div className="px-5 py-3">
        <Input value={find} onChange={(e) => setFind(e.target.value)} placeholder="Find a customer, TIN or invoice" aria-label="Find a customer, TIN or invoice" className="max-w-xs" />
      </div>
      <div className="max-h-[30rem] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-sheet">
            <tr className="text-left text-meta text-ink-3">
              {["Customer", "TIN", "Invoices", "Exempt", "Zero-rated", "VATable", "Output VAT"].map((h, i) => (
                <th key={h} className={`px-5 py-1 font-medium ${i >= 2 ? "text-right" : ""}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.slice(0, 600).map((r) => {
              const parts = r.parts || [r], many = parts.length > 1, k = key(r), isOpen = many && open[k];
              return [
                <tr key={k} className={`border-t border-rule ${many ? "cursor-pointer hover:bg-hema-tint" : ""}`} onClick={many ? () => setOpen((x) => ({ ...x, [k]: !x[k] })) : undefined}>
                  <td className="px-5 py-1.5">{many ? (isOpen ? "▾ " : "▸ ") : ""}{r.name}</td>
                  <td className="px-5 py-1.5 font-mono">{r.tin || "—"}</td>
                  <td className="px-5 py-1.5 text-right">{many ? parts.length : r.inv?.si || 1}</td>
                  <td className="px-5 py-1.5 text-right font-mono tabular-nums">{peso(r.exempt)}</td>
                  <td className="px-5 py-1.5 text-right font-mono tabular-nums">{peso(r.zero)}</td>
                  <td className="px-5 py-1.5 text-right font-mono tabular-nums">{peso(r.taxable)}</td>
                  <td className="px-5 py-1.5 text-right font-mono tabular-nums">{peso(r.vat)}</td>
                </tr>,
                ...(isOpen
                  ? parts.map((p: Any, i: number) => (
                      <tr key={`${k}-${i}`} className="bg-bench text-meta text-ink-2">
                        <td className="py-1 pr-5 pl-10">
                          {p.inv?.si || "(no invoice matched)"}{p.inv?.added ? " (added)" : ""}
                          <span className="block text-ink-3">{[p.inv?.date, p.inv?.sjRow && `Sales Journal row ${p.inv.sjRow}`].filter(Boolean).join(" · ")}</span>
                        </td>
                        <td />
                        <td />
                        <td className="px-5 py-1 text-right font-mono tabular-nums">{peso(p.exempt)}</td>
                        <td className="px-5 py-1 text-right font-mono tabular-nums">{peso(p.zero)}</td>
                        <td className="px-5 py-1 text-right font-mono tabular-nums">{peso(p.taxable)}</td>
                        <td className="px-5 py-1 text-right font-mono tabular-nums">{peso(p.vat)}</td>
                      </tr>
                    ))
                  : []),
              ];
            })}
            {shown.length > 600 && <tr><td colSpan={7} className="px-5 py-2 text-meta text-ink-3">{shown.length - 600} more: use Find.</td></tr>}
            {!shown.length && <tr><td colSpan={7} className="px-5 py-2 text-meta text-ink-3">No line matches.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function namesNote(rows: Any[]) {
  const ch = nameChanges(rows), check = ch.filter((x: Any) => x.check).length;
  return `${ch.length} spelled differently in the DAT${check ? ` · ${check} worth checking` : ""}`;
}

function Names({ rows }: { rows: Any[] }) {
  const ch = nameChanges(rows);
  return (
    <>
      <p className="px-5 pt-3 text-meta text-ink-3">If a name comes out wrong, tell {CONFIRMED_BY}: it becomes a ruling (by TIN), which always wins over the rules.</p>
      <Table head={["Name in Oojeema", "Name in the DAT", "Why"]} rows={ch.map((x: Any) => [x.original, x.dat, x.why === "Exceptions list" ? "Exceptions list" : x.check ? "Rules: worth checking" : "Rules"])} />
    </>
  );
}

function Checks({ checks }: { checks: Any[] }) {
  return (
    <ul className="space-y-1 px-5 py-3 text-sm">
      {checks.map((c) => (
        <li key={c.label} className={c.ok ? "" : "text-danger"}>
          <span className="inline-block w-5 font-mono">{c.ok ? "✓" : "✗"}</span>
          {c.label}
        </li>
      ))}
    </ul>
  );
}

function GlRoles({ L, roles, onChange }: { L: Loaded; roles: Record<string, Role>; onChange: (name: string, role: Role) => void }) {
  const names = L.gl ? Object.keys(L.gl.accounts) : [];
  if (!names.length) return null;
  return (
    <div>
      <p className="font-medium">What each General Ledger account is used for</p>
      <p className="text-meta text-ink-3">Set automatically from the account name. Change only if an account was recognised wrongly.</p>
      <div className="mt-2 grid gap-3 sm:grid-cols-2">
        {names.map((n) => (
          <Field key={n} label={`${n} (${L.gl.accounts[n].n} entries)`}>
            {(p) => (
              <Select {...p} value={roles[n] || "ignore"} onChange={(e) => onChange(n, e.target.value as Role)}>
                {ROLE_LABEL.map(([v, label]) => (
                  <option key={v} value={v}>{label}</option>
                ))}
              </Select>
            )}
          </Field>
        ))}
      </div>
    </div>
  );
}

function RulesList() {
  return (
    <div className="px-5 py-3 text-sm">
      <ol className="list-decimal space-y-2 pl-5">
        {RULES.map((r) => (
          <li key={r.title}>
            <b>{r.title}.</b> {r.detail} <span className="text-meta text-ink-3">Confirmed by {CONFIRMED_BY}, {r.confirmed}.</span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-ink-2">{OTHERWISE}</p>
    </div>
  );
}
