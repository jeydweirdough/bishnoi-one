"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { loadSupplierReview, saveSupplierReview } from "./actions";
import type { SupplierReviewChange, SupplierReviewList, SupplierReviewRow } from "./supplier-review-types";

type Edit = { before: SupplierReviewRow; after: SupplierReviewRow };
const control = "h-9 max-w-full rounded border border-rule-strong bg-sheet px-2 text-sm text-ink";
const where = (s: SupplierReviewRow) => s.origin === "local" ? "Local" : s.origin === "foreign" ? "Foreign" : "Not set";

/** Editing is visible in the list; review stays in the same workspace. */
export function SupplierReview({ initial, initialQuery, org }: { initial: SupplierReviewList; initialQuery: string; org: Org }) {
  const fmt = makeFormat(org);
  const [list, setList] = useState(initial);
  const [search, setSearch] = useState(initialQuery);
  const [origin, setOrigin] = useState("");
  const [noCode, setNoCode] = useState(false);
  const [pageSize, setPageSize] = useState(initial.pageSize);
  const [companyUse, setCompanyUse] = useState("2mg");
  const [applied, setApplied] = useState({ search: initialQuery, origin: "", noCode: false, pageSize: initial.pageSize, companyUse: "2mg" });
  const [selected, setSelected] = useState<Record<string, SupplierReviewRow>>({});
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  const [bulkOrigin, setBulkOrigin] = useState("");
  const [bulkCode, setBulkCode] = useState("keep");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const statusRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (message) statusRef.current?.focus(); }, [message]);
  const changes = Object.values(edits);
  const picks = Object.values(selected);
  const visibleIds = new Set(list.items.map(s => s.id));
  const hidden = picks.filter(s => !visibleIds.has(s.id)).length;
  const conflicts = changes.filter(e => e.after.origin === "foreign" && !!e.after.withholding);
  useEffect(() => {
    if (!changes.length) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [changes.length]);
  const codeLabel = (code: string | null) => {
    if (!code) return "No usual code";
    const option = list.withholding.find(w => w.code === code);
    return option ? `${code} · ${option.rateBp / 100}%` : `${code} · rate not available`;
  };

  function edit(rows: SupplierReviewRow[], patch: Partial<Pick<SupplierReviewRow, "origin" | "withholding">>) {
    setError(""); setMessage("");
    setEdits(previous => {
      const next = { ...previous };
      for (const row of rows) {
        const before = next[row.id]?.before ?? row;
        const after = { ...(next[row.id]?.after ?? row), ...patch };
        if (before.origin === after.origin && before.withholding === after.withholding) delete next[row.id];
        else next[row.id] = { before, after };
      }
      return next;
    });
  }

  async function load(page: number, applyFilters = false) {
    setBusy(true); setError("");
    try {
      const filters = applyFilters ? { search, origin, noCode, pageSize, companyUse } : applied;
      const params = new URLSearchParams({ q: filters.search, page: String(page), page_size: String(filters.pageSize) });
      if (filters.origin) params.set("origin", filters.origin);
      if (filters.noCode) params.set("no_code", "true");
      params.set("company_use", filters.companyUse);
      const result = await loadSupplierReview(params.toString());
      if (!result.ok) setError(result.error);
      else { setList(result.data); setApplied(filters); }
    } catch { setError("The list could not be loaded. Your unsaved changes are still here."); }
    finally { setBusy(false); }
  }

  async function save() {
    if (busy || uncertain || !changes.length || conflicts.length || changes.length > 100) return;
    setBusy(true); setSaving(true); setError(""); setMessage("");
    const payload: SupplierReviewChange[] = changes.map(({ before, after }) => ({
      id: before.id, version: before.version,
      ...(after.origin !== before.origin && after.origin ? { origin: after.origin } : {}),
      ...(after.withholding !== before.withholding ? { withholding: after.withholding } : {}),
    }));
    try {
      const result = await saveSupplierReview(payload);
      if (!result.ok) { setError(result.error); setUncertain(!!result.uncertain); return; }
      const updated = new Map(result.data.items.map(s => [s.id, s]));
      setList(current => ({ ...current, items: current.items.map(s => updated.get(s.id) ?? s) }));
      setEdits({}); setSelected({});
      setMessage(`Saved ${result.data.changed} supplier${result.data.changed === 1 ? "" : "s"}. Existing bills were not changed.`);
    } catch {
      setUncertain(true); setError("The save result is unknown. Reload saved values before making another change.");
    } finally { setBusy(false); setSaving(false); }
  }

  return <div className="space-y-4">
    {list.reconciliation && <section className="space-y-2 rounded border border-rule bg-sheet p-3" aria-label="2MG export reconciliation">
      <p className="text-sm">2MG Oojeema export: <strong>{list.reconciliation.sourceRows} source rows</strong> · {list.reconciliation.matchedRows} linked to existing suppliers · {list.reconciliation.createdRows} newly added · {list.reconciliation.issues.length} identity issues. Trade-name aliases can link to one supplier.</p>
      {!!list.reconciliation.issues.length && <details><summary className="cursor-pointer text-sm font-semibold text-hema">View {list.reconciliation.issues.length} source identity issues</summary><p className="my-2 text-meta">These are 2MG source vendors whose existing-record link needs resolving. A missing tax code is a separate issue. No supplier has been deleted.</p><div className="max-h-80 overflow-auto" tabIndex={0}><table className="w-full text-sm"><thead><tr className="text-left"><th className="p-2">Source row</th><th className="p-2">Vendor</th><th className="p-2">Code / TIN</th><th className="p-2">Reason</th></tr></thead><tbody>{list.reconciliation.issues.map(r => <tr key={r.line} className="border-t border-rule"><td className="p-2">{r.line}</td><td className="p-2">{r.name}</td><td className="p-2">{r.code} · {r.tin || "No TIN"}</td><td className="p-2">{{ conflicting_tax_identity: "Conflicting tax identity", unresolved_existing_identity: "Existing identity not resolved", source_vendor_not_yet_linked: "Duplicate source tax identity" }[r.reason] ?? r.reason}</td></tr>)}</tbody></table></div></details>}
    </section>}
    <form className="flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void load(1, true); }}>
      <label className="grid gap-1 text-meta">Company use<select className={control} value={companyUse} disabled={busy || uncertain} onChange={e => setCompanyUse(e.target.value)}><option value="2mg">Verified 2MG suppliers</option><option value="review">Other saved suppliers</option><option value="all">All saved suppliers</option></select></label>
      <label className="grid gap-1 text-meta">Find supplier<input className={control} value={search} onChange={e => setSearch(e.target.value)} placeholder="Name, company or TIN" disabled={busy || uncertain} /></label>
      <label className="grid gap-1 text-meta">Local / Foreign<select className={control} value={origin} onChange={e => setOrigin(e.target.value)} disabled={busy || uncertain}><option value="">All suppliers</option><option value="local">Local</option><option value="foreign">Foreign</option><option value="unset">Not set</option></select></label>
      <label className="flex min-h-9 items-center gap-2 text-sm"><input type="checkbox" checked={noCode} onChange={e => setNoCode(e.target.checked)} disabled={busy || uncertain} />No usual tax code</label>
      <label className="grid gap-1 text-meta">Per page<select className={control} value={pageSize} disabled={busy || uncertain} onChange={e => setPageSize(Number(e.target.value))}>{[25, 50, 100].map(n => <option key={n} value={n}>{n}</option>)}</select></label>
      <Button disabled={busy || uncertain} type="submit">Search / filter</Button>
    </form>
    <p className="text-meta text-ink-3">Edit directly in the table. Local/Foreign is a supplier classification; importation is a bill purchase type. No usual code means no default is selected.</p>
    {list.canEdit && <div className="flex flex-wrap items-end gap-3 rounded border border-rule bg-bench/30 p-3">
      <p className="self-center text-sm font-semibold">{picks.length} selected suppliers{hidden ? ` · ${hidden} outside this page` : ""}</p>
      <label className="grid gap-1 text-meta">Set classification<select className={control} value={bulkOrigin} onChange={e => setBulkOrigin(e.target.value)} disabled={busy || uncertain}><option value="">Keep current</option><option value="local">Local</option><option value="foreign">Foreign</option></select></label>
      <label className="grid gap-1 text-meta">Set usual tax code<select className={`${control} w-72`} value={bulkCode} onChange={e => setBulkCode(e.target.value)} disabled={busy || uncertain}><option value="keep">Keep current</option><option value="clear">Clear usual code</option>{list.withholding.map(w => <option key={w.code} value={w.code}>{w.code} · {w.name} · {w.rateBp / 100}%</option>)}</select></label>
      <Button type="button" disabled={busy || uncertain || !picks.length || (!bulkOrigin && bulkCode === "keep")} onClick={() => edit(picks, { ...(bulkOrigin ? { origin: bulkOrigin as "local" | "foreign" } : {}), ...(bulkCode !== "keep" ? { withholding: bulkCode === "clear" ? null : bulkCode } : {}) })}>Apply to selected</Button>
      {!!picks.length && <Button type="button" disabled={busy} onClick={() => setSelected({})}>Clear selection</Button>}
    </div>}
    {!!changes.length && <section aria-label="Review supplier changes" className="sticky top-0 z-20 space-y-3 rounded border border-rule-strong bg-sheet p-3 shadow-sm">
      <h2 className="font-semibold">Review {changes.length} changed supplier{changes.length === 1 ? "" : "s"}</h2>
      <p className="text-meta">Only the fields shown below will change. Existing bills stay unchanged. Edited supplier tax defaults will need confirming on a bill before they fill future bills.</p>
      <div className="max-h-24 overflow-auto" tabIndex={0} aria-label="Before and after values"><ul className="space-y-2 text-sm">{changes.map(({ before, after }) => <li key={before.id}><strong>{before.name}</strong>{before.origin !== after.origin && <span> · {where(before)} → {where(after)}</span>}{before.withholding !== after.withholding && <span> · {codeLabel(before.withholding)} → {codeLabel(after.withholding)}</span>}{after.origin === "foreign" && after.withholding && <span className="block font-semibold">Clear the tax code or keep this supplier Local before saving.</span>}</li>)}</ul></div>
      {changes.length > 100 && <p role="alert">Save at most 100 changed suppliers at a time. Discard extra edits before saving.</p>}
      <div className="flex flex-wrap gap-2"><Button type="button" variant="primary" disabled={busy || uncertain || !!conflicts.length || changes.length > 100} onClick={() => void save()}>{saving ? "Saving…" : `Save ${changes.length} supplier${changes.length === 1 ? "" : "s"}`}</Button><Button type="button" disabled={busy || uncertain} onClick={() => { setEdits({}); setError(""); }}>Discard changes</Button></div>
    </section>}
    {error && <div role="alert" className="space-y-2 rounded border border-rule-strong p-3"><p>{error}</p><p className="text-meta">Reloading replaces this view and discards unsaved changes.</p><Button type="button" disabled={busy} onClick={() => window.location.reload()}>Reload saved values</Button></div>}
    {message && <p ref={statusRef} tabIndex={-1} role="status" className="text-sm">{message}</p>}
    <div className="overflow-x-auto rounded border border-rule bg-sheet" aria-busy={busy}>
      <table className="w-full min-w-[48rem] text-sm"><caption className="sr-only">Suppliers with directly editable classification and usual withholding tax code</caption><thead><tr className="border-b border-rule text-left text-meta">
        {list.canEdit && <th className="p-3"><input type="checkbox" aria-label="Select suppliers on this page only" disabled={busy || uncertain || !list.items.length} checked={!!list.items.length && list.items.every(s => !!selected[s.id])} onChange={e => { const checked = e.target.checked; setSelected(previous => { const next = { ...previous }; for (const s of list.items) { if (checked) next[s.id] = s; else delete next[s.id]; } return next; }); }} /></th>}
        <th className="p-3">Supplier / contact</th><th className="p-3">Local / Foreign</th><th className="p-3">Usual tax withheld</th><th className="p-3">Tax defaults</th><th className="p-3 text-right">Payables</th>
      </tr></thead><tbody>{list.items.map(saved => {
        const row = edits[saved.id]?.after ?? saved;
        return <tr key={row.id} className={`border-b border-rule ${edits[row.id] ? "bg-bench/50" : ""}`}>
          {list.canEdit && <td className="p-3"><input type="checkbox" aria-label={`Select ${row.name}`} checked={!!selected[row.id]} disabled={busy || uncertain} onChange={e => { const checked = e.target.checked; setSelected(previous => { const next = { ...previous }; if (checked) next[row.id] = saved; else delete next[row.id]; return next; }); }} /></td>}
          <td className="p-3"><Link className="font-semibold text-hema underline" href={`/finance/suppliers/${row.id}`} onClick={e => { if (changes.length) { e.preventDefault(); setError("Save or discard your list changes before opening supplier details."); } }}>{row.name}</Link><span className="block text-meta">{row.companyName}</span><span className="block text-meta">{row.tin ? `TIN ${row.tin}${row.branchCode ? `-${row.branchCode}` : ""}` : "No TIN"}</span><span className="block text-meta">{[row.email, row.phone].filter(Boolean).join(" · ")}</span>{!row.isActive && <span className="block text-meta">Switched off</span>}{!!edits[row.id] && <span className="block text-meta">Unsaved change</span>}</td>
          <td className="p-3">{list.canEdit ? <select aria-label={`${row.name}: Local or Foreign`} className={control} value={row.origin ?? ""} disabled={busy || uncertain} onChange={e => edit([saved], { origin: e.target.value as "local" | "foreign" })}><option value="" disabled>Not set</option><option value="local">Local</option><option value="foreign">Foreign</option></select> : where(row)}</td>
          <td className="p-3">{list.canEdit ? <select aria-label={`${row.name}: usual tax withheld`} className={`${control} w-80`} value={row.withholding ?? ""} disabled={busy || uncertain} onChange={e => edit([saved], { withholding: e.target.value || null })}><option value="">No usual code</option>{list.withholding.map(w => <option key={w.code} value={w.code}>{w.code} · {w.name} · {w.rateBp / 100}%</option>)}</select> : codeLabel(row.withholding)}</td>
          <td className="p-3 text-meta">{edits[row.id] ? "Will need confirmation" : row.taxDefaultsConfirmed ? "Confirmed" : "Confirm on bill"}</td>
          <td className="p-3 text-right tabular-nums">{fmt.peso(row.owedCentavos)}</td>
        </tr>;
      })}{!list.items.length && <tr><td className="p-5" colSpan={list.canEdit ? 6 : 5}>No suppliers match these filters.</td></tr>}</tbody></table>
    </div>
    <div className="flex flex-wrap items-center justify-between gap-3 text-sm"><p>{list.total} matching suppliers · Page {list.page} of {list.pages} · {list.items.length} on this page</p><div className="flex flex-wrap gap-2"><Button type="button" disabled={busy || uncertain || list.page <= 1} onClick={() => void load(1)}>First</Button><Button type="button" disabled={busy || uncertain || list.page <= 1} onClick={() => void load(list.page - 1)}>Previous</Button><Button type="button" disabled={busy || uncertain || list.page >= list.pages} onClick={() => void load(list.page + 1)}>Next</Button><Button type="button" disabled={busy || uncertain || list.page >= list.pages} onClick={() => void load(list.pages)}>Last</Button></div></div>
  </div>;
}
