"use client";

import { Dropdown, Modal } from "antd";
import { ChevronDown, Download, FileText, Plus, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/src/platform/ui/button";
import { Input, Textarea } from "@/src/platform/ui/field";
import type { ColumnKind } from "./types";

// Save as (owner, 2026-11-19): every report saves as a proper document instead of printing the screen.
// A preview first, as it will be saved: the company's letterhead, the report's details (period, filters,
// search, rows, who made it and when), its figures and rows, remarks, and signatories with their names
// and positions. "Save as PDF" prints only the document (the browser's dialog saves it as PDF); Excel
// (CSV) exports the same rows. The signatories are remembered on this computer for the next report.

/** What the document says around the rows, worked out by the page (src/platform/reports/report-view.tsx). */
export type ReportDoc = {
  company: { legalName: string; address: string | null; tin: string | null; phone: string | null; email: string | null; logo: string | null; footer: string | null };
  /** "Customers and selling", "Employees": the part of Bishnoi One it comes from. */
  source?: string;
  period?: string | null;
  filters?: { label: string; value: string }[];
  summary?: { label: string; value: string }[];
  notes?: string[];
  preparedBy: { name: string; title: string | null };
};

type Col = { key: string; label: string; kind: ColumnKind };
type Signatory = { role: string; name: string; title: string };

const numeric = (k: ColumnKind) => k === "money" || k === "number" || k === "percent";
const KEPT = "bishnoi-report-signatories";

function remembered(me: ReportDoc["preparedBy"]): Signatory[] {
  const mine = { role: "Prepared by", name: me.name, title: me.title ?? "" };
  try {
    const kept = JSON.parse(localStorage.getItem(KEPT) ?? "null") as Signatory[] | null;
    if (Array.isArray(kept) && kept.length > 0) return [mine, ...kept.filter((s) => s.role !== "Prepared by").slice(0, 3)];
  } catch {
    /* nothing kept */
  }
  return [mine, { role: "Checked by", name: "", title: "" }, { role: "Approved by", name: "", title: "" }];
}

export function SaveAs({
  title,
  columns,
  rows,
  totals,
  search,
  allRows,
  doc,
  onCsv,
}: {
  title: string;
  columns: Col[];
  /** The rows as shown: sorted and searched. */
  rows: string[][];
  totals: (string | null)[] | null;
  search: string;
  allRows: number;
  doc?: ReportDoc;
  /** Excel (CSV) of the same rows; absent when the person may not export. */
  onCsv?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const items = [
    { key: "pdf", icon: <FileText className="size-4" aria-hidden />, label: "PDF document", onClick: () => setOpen(true) },
    ...(onCsv ? [{ key: "csv", icon: <Download className="size-4" aria-hidden />, label: "Excel (CSV)", onClick: onCsv }] : []),
  ];
  return (
    <>
      <Dropdown menu={{ items }} trigger={["click"]} placement="bottomRight">
        <button suppressHydrationWarning type="button" className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-rule bg-white px-3 text-sm text-ink hover:border-ink">
          <Save className="size-4" aria-hidden /> Save as <ChevronDown className="size-3.5 text-ink-3" aria-hidden />
        </button>
      </Dropdown>
      {open && <Preview title={title} columns={columns} rows={rows} totals={totals} search={search} allRows={allRows} doc={doc} onClose={() => setOpen(false)} />}
    </>
  );
}

function Preview({ title, columns, rows, totals, search, allRows, doc, onClose }: { title: string; columns: Col[]; rows: string[][]; totals: (string | null)[] | null; search: string; allRows: number; doc?: ReportDoc; onClose: () => void }) {
  const me = doc?.preparedBy ?? { name: "", title: null };
  const [heading, setHeading] = useState(title);
  const [remarks, setRemarks] = useState("");
  const [signers, setSigners] = useState<Signatory[]>(() => remembered(me));
  const [made] = useState(() => new Date());
  const [printing, setPrinting] = useState(false);

  useEffect(() => {
    const done = () => {
      document.documentElement.classList.remove("report-doc-printing");
      setPrinting(false);
    };
    window.addEventListener("afterprint", done);
    return () => {
      window.removeEventListener("afterprint", done);
      document.documentElement.classList.remove("report-doc-printing");
    };
  }, []);

  function save() {
    try {
      localStorage.setItem(KEPT, JSON.stringify(signers.filter((s) => s.role !== "Prepared by")));
    } catch {
      /* private window: not kept */
    }
    const before = document.title;
    // The browser names the PDF after the page's title.
    document.title = `${heading} ${made.toISOString().slice(0, 10)}`;
    setPrinting(true);
    document.documentElement.classList.add("report-doc-printing");
    requestAnimationFrame(() => {
      window.print();
      document.title = before;
    });
  }

  const set = (i: number, patch: Partial<Signatory>) => setSigners((all) => all.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const paper = (
    <ReportPaper heading={heading} columns={columns} rows={rows} totals={totals} search={search} allRows={allRows} doc={doc} remarks={remarks} signers={signers.filter((s) => s.role.trim())} made={made} />
  );

  return (
    <>
      <Modal
        open
        onCancel={onClose}
        width={1180}
        title="Save as PDF document"
        footer={
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-meta text-ink-3">In the dialog that opens, choose &ldquo;Save as PDF&rdquo; as the printer.</span>
            <span className="inline-flex gap-2">
              <Button onClick={onClose}>Close</Button>
              <Button variant="primary" icon={<FileText className="size-4" aria-hidden />} onClick={save}>
                Save as PDF
              </Button>
            </span>
          </div>
        }
        destroyOnHidden
      >
        <div className="grid gap-5 pt-2 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1 block text-meta font-medium text-ink-2">Document title</span>
              <Input value={heading} onChange={(e) => setHeading(e.target.value)} maxLength={140} />
            </label>
            <label className="block">
              <span className="mb-1 block text-meta font-medium text-ink-2">Remarks (optional)</span>
              <Textarea value={remarks} onChange={(e) => setRemarks(e.target.value)} rows={3} maxLength={1000} placeholder="Shown above the signatures" />
            </label>
            <div>
              <p className="mb-1 text-meta font-medium text-ink-2">Signatories</p>
              <ul className="space-y-3">
                {signers.map((s, i) => (
                  <li key={i} className="rounded-lg border border-rule p-2.5">
                    <div className="flex items-center gap-2">
                      <Input aria-label="Signs as" value={s.role} onChange={(e) => set(i, { role: e.target.value })} maxLength={40} placeholder="Signs as" />
                      {i > 0 && (
                        <button type="button" aria-label={`Remove ${s.role || "this signatory"}`} onClick={() => setSigners((all) => all.filter((_, j) => j !== i))} className="grid size-9 shrink-0 place-items-center rounded-md text-ink-3 hover:bg-bench hover:text-ink">
                          <X className="size-4" aria-hidden />
                        </button>
                      )}
                    </div>
                    <Input className="mt-2" aria-label="Name" value={s.name} onChange={(e) => set(i, { name: e.target.value })} maxLength={80} placeholder="Name" />
                    <Input className="mt-2" aria-label="Position" value={s.title} onChange={(e) => set(i, { title: e.target.value })} maxLength={80} placeholder="Position" />
                  </li>
                ))}
              </ul>
              {signers.length < 4 && (
                <button type="button" onClick={() => setSigners((all) => [...all, { role: "Noted by", name: "", title: "" }])} className="mt-2 inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink hover:underline">
                  <Plus className="size-4" aria-hidden /> Add a signatory
                </button>
              )}
            </div>
          </div>
          <div className="max-h-[70vh] overflow-auto rounded-xl bg-bench p-4">
            <div className="mx-auto w-full max-w-[210mm] bg-white shadow-sm">{paper}</div>
          </div>
        </div>
      </Modal>
      {/* What the browser prints: only this, while saving (app/globals.css .report-doc-printing). */}
      {printing && createPortal(<div id="report-doc-print">{paper}</div>, document.body)}
    </>
  );
}

const when = (d: Date) => d.toLocaleString("en-PH", { day: "numeric", month: "long", year: "numeric", hour: "numeric", minute: "2-digit" });

/** The document itself, on screen in the preview and on paper. */
function ReportPaper({
  heading,
  columns,
  rows,
  totals,
  search,
  allRows,
  doc,
  remarks,
  signers,
  made,
}: {
  heading: string;
  columns: Col[];
  rows: string[][];
  totals: (string | null)[] | null;
  search: string;
  allRows: number;
  doc?: ReportDoc;
  remarks: string;
  signers: Signatory[];
  made: Date;
}) {
  const c = doc?.company;
  const contacts = [c?.phone, c?.email].filter(Boolean).join(" · ");
  const details: [string, string][] = [
    ...(doc?.source ? ([["Source", doc.source]] as [string, string][]) : []),
    ...(doc?.period ? ([["Period", doc.period]] as [string, string][]) : []),
    ...(doc?.filters ?? []).map((f) => [f.label, f.value] as [string, string]),
    ...(search.trim() ? ([["Rows matching", `“${search.trim()}”`]] as [string, string][]) : []),
    ["Rows", rows.length === allRows ? String(allRows) : `${rows.length} of ${allRows}`],
    ["Generated on", when(made)],
    ["Generated by", [doc?.preparedBy.name, doc?.preparedBy.title].filter(Boolean).join(", ") || "—"],
  ];
  return (
    <article className="report-paper px-[14mm] py-[12mm] text-[9.5pt] leading-snug text-black">
      <header className="flex items-start justify-between gap-6 border-b-2 border-black pb-3">
        <div className="flex items-start gap-3">
          {c?.logo && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={c.logo} alt="" className="h-14 max-w-[40mm] object-contain" />
          )}
          <div>
            <p className="text-[14pt] leading-tight font-bold">{c?.legalName}</p>
            {c?.address && <p className="text-[8.5pt]">{c.address}</p>}
            {c?.tin && <p className="text-[8.5pt]">TIN {c.tin}</p>}
            {contacts && <p className="text-[8.5pt]">{contacts}</p>}
          </div>
        </div>
        <div className="text-right">
          <p className="text-[8pt] font-semibold tracking-wider uppercase">Report</p>
          <h1 className="text-[14pt] leading-tight font-bold">{heading}</h1>
          {doc?.period && <p className="text-[8.5pt]">{doc.period}</p>}
        </div>
      </header>

      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-0.5 text-[8.5pt]">
        {details.map(([k, v]) => (
          <div key={k} className="flex gap-2 border-b border-dotted border-neutral-300 py-0.5">
            <dt className="w-28 shrink-0 font-semibold">{k}</dt>
            <dd className="min-w-0">{v}</dd>
          </div>
        ))}
      </dl>

      {doc?.summary && doc.summary.length > 0 && (
        <div className="mt-3 grid grid-cols-4 gap-2">
          {doc.summary.map((f) => (
            <div key={f.label} className="rounded border border-neutral-300 px-2 py-1.5">
              <p className="text-[7.5pt] text-neutral-600">{f.label}</p>
              <p className="text-[11pt] font-bold tabular-nums">{f.value}</p>
            </div>
          ))}
        </div>
      )}

      <table className="mt-4 w-full border-collapse text-[8.5pt]">
        <thead className="[display:table-header-group]">
          <tr className="border-y border-black">
            {columns.map((col) => (
              <th key={col.key} scope="col" className={`px-1.5 py-1 font-semibold ${numeric(col.kind) ? "text-right" : "text-left"}`}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-1.5 py-3 text-center text-neutral-600">No rows.</td>
            </tr>
          ) : (
            rows.map((r, ri) => (
              <tr key={ri} className="break-inside-avoid border-b border-neutral-200">
                {r.map((t, i) => (
                  <td key={columns[i].key} className={`px-1.5 py-0.5 align-top ${numeric(columns[i].kind) ? "text-right whitespace-nowrap tabular-nums" : ""}`}>
                    {t || "—"}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
        {totals && rows.length > 0 && (
          <tfoot>
            <tr className="border-y-2 border-black font-bold">
              {totals.map((t, i) => (
                <td key={columns[i].key} className={`px-1.5 py-1 ${numeric(columns[i].kind) ? "text-right tabular-nums" : ""}`}>
                  {t ?? (i === 0 ? "Total" : "")}
                </td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>

      {doc?.notes && doc.notes.length > 0 && (
        <ul className="mt-3 list-disc pl-4 text-[8pt] text-neutral-700">
          {doc.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}

      {remarks.trim() && (
        <section className="mt-4 break-inside-avoid">
          <p className="text-[8pt] font-semibold tracking-wider uppercase">Remarks</p>
          <p className="mt-0.5 whitespace-pre-line">{remarks}</p>
        </section>
      )}

      {signers.length > 0 && (
        <section className="mt-8 grid break-inside-avoid gap-6" style={{ gridTemplateColumns: `repeat(${Math.min(signers.length, 4)}, minmax(0, 1fr))` }}>
          {signers.map((s, i) => (
            <div key={i}>
              <p className="text-[8pt]">{s.role}:</p>
              <div className="mt-9 border-b border-black" />
              <p className="mt-1 font-semibold">{s.name || "00a0"}</p>
              <p className="text-[8pt]">{s.title || "00a0"}</p>
              <p className="mt-2 text-[8pt]">Date: ____________________</p>
            </div>
          ))}
        </section>
      )}

      <footer className="mt-8 flex items-end justify-between gap-4 border-t border-neutral-300 pt-1.5 text-[7.5pt] text-neutral-600">
        <span>{c?.footer}</span>
        <span>Generated by Bishnoi One · {when(made)}</span>
      </footer>
    </article>
  );
}
