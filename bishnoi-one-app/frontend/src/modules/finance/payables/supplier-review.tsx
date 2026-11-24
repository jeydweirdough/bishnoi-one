"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { approveSuppliersFor2mg, loadSupplierReview, saveSupplierReview } from "./actions";
import type { SupplierReviewChange, SupplierReviewList, SupplierReviewRow } from "./supplier-review-types";

type Edit = { before: SupplierReviewRow; after: SupplierReviewRow };
const control = "h-9 max-w-full rounded border border-rule-strong bg-sheet px-2 text-sm text-ink";
const where = (s: SupplierReviewRow) => s.origin === "local" ? "Local" : s.origin === "foreign" ? "Foreign" : "Not set";

/** Editing is visible in the list; review stays in the same workspace. */
export function SupplierReview({ initial, initialQuery, org, canApprove2mg = false }: { initial: SupplierReviewList; initialQuery: string; org: Org; canApprove2mg?: boolean }) {
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
    if (applyFilters && companyUse !== applied.companyUse && changes.length) { setError("Save or discard changes before switching between 2MG suppliers and retained history."); return; }
    setBusy(true); setError("");
    try {
      const filters = applyFilters ? { search, origin, noCode, pageSize, companyUse } : applied;
      const params = new URLSearchParams({ q: filters.search, page: String(page), page_size: String(filters.pageSize) });
      if (filters.origin) params.set("origin", filters.origin);
      if (filters.noCode) params.set("no_code", "true");
      params.set("company_use", filters.companyUse);
      const result = await loadSupplierReview(params.toString());
      if (!result.ok) setError(result.error);
      else { if (filters.companyUse !== applied.companyUse) setSelected({}); setList(result.data); setApplied(filters); }
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

  async function approveFor2mg() {
    if (busy || uncertain || !picks.length) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await approveSuppliersFor2mg(picks.map(p => p.id));
      if (!result.ok) { setError(result.error); return; }
      setSelected({});
      setMessage(`Approved ${result.data.approved} supplier${result.data.approved === 1 ? "" : "s"} for 2MG.`);
      await load(list.page);
    } catch {
      setError("Could not approve the selected suppliers for 2MG.");
    } finally { setBusy(false); }
  }

  const showSelection = list.canEdit || (applied.companyUse !== "2mg" && canApprove2mg);

  return <div className="space-y-4">
    {list.reconciliation && <section className="space-y-2 rounded border border-rule bg-sheet p-3" aria-label="2MG export reconciliation">
      <p className="text-sm">2MG Oojeema export: <strong>{list.reconciliation.sourceRows} source rows</strong> · {list.reconciliation.matchedRows} linked to existing suppliers · {list.reconciliation.createdRows} newly added · {list.reconciliation.issues.length} identity issues. Trade-name aliases can link to one supplier.</p>
      {!!list.reconciliation.issues.length && <details><summary className="cursor-pointer text-sm font-semibold text-hema">View {list.reconciliation.issues.length} source identity issues</summary><p className="my-2 text-meta">These are 2MG source vendors whose existing-record link needs resolving. A missing tax code is a separate issue. No supplier has been deleted.</p><div className="max-h-80 overflow-auto" tabIndex={0}><table className="w-full text-sm"><thead><tr className="text-left"><th className="p-2">Source row</th><th className="p-2">Vendor</th><th className="p-2">Code / TIN</th><th className="p-2">Reason</th></tr></thead><tbody>{list.reconciliation.issues.map(r => <tr key={r.line} className="border-t border-rule"><td className="p-2">{r.line}</td><td className="p-2">{r.name}</td><td className="p-2">{r.code} · {r.tin || "No TIN"}</td><td className="p-2">{{ conflicting_tax_identity: "Conflicting tax identity", unresolved_existing_identity: "Existing identity not resolved", source_vendor_not_yet_linked: "Duplicate source tax identity" }[r.reason] ?? r.reason}</td></tr>)}</tbody></table></div></details>}
    </section>}
    <form className="flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void load(1, true); }}>
      <label className="grid gap-1 text-meta">Company use<select className={control} value={companyUse} disabled={busy || uncertain} onChange={e => setCompanyUse(e.target.value)}><option value="2mg">Suppliers in use</option><option value="history">Retained history (read only)</option></select></label>
      <label className="grid gap-1 text-meta">Find supplier<input className={control} value={search} onChange={e => setSearch(e.target.value)} placeholder="Name, company or TIN" disabled={busy || uncertain} /></label>
      <label className="grid gap-1 text-meta">Local / Foreign<select className={control} value={origin} onChange={e => setOrigin(e.target.value)} disabled={busy || uncertain}><option value="">All suppliers</option><option value="local">Local</option><option value="foreign">Foreign</option><option value="unset">Not set</option></select></label>
      <label className="flex min-h-9 items-center gap-2 text-sm"><input type="checkbox" checked={noCode} onChange={e => setNoCode(e.target.checked)} disabled={busy || uncertain} />No usual tax code</label>
      <label className="grid gap-1 text-meta">Per page<select className={control} value={pageSize} disabled={busy || uncertain} onChange={e => setPageSize(Number(e.target.value))}>{[25, 50, 100].map(n => <option key={n} value={n}>{n}</option>)}</select></label>
      <Button disabled={busy || uncertain} type="submit">Search / filter</Button>
    </form>
    {applied.companyUse !== "2mg" && <p role="status" className="rounded border border-rule bg-bench/30 p-3 text-sm">Retained records are read only. They support existing history and are not verified for new 2MG work. Being outside the verified list does not prove a supplier is GPI-only.</p>}
    <p className="text-meta text-ink-3">Edit verified 2MG suppliers directly in the table. Local/Foreign is a supplier classification; importation is a bill purchase type. No usual code means no default is selected.</p>
    {applied.companyUse !== "2mg" && canApprove2mg && <div className="flex flex-wrap items-center gap-3 rounded border border-rule bg-bench/30 p-3">
      <p className="text-sm font-semibold">{picks.length} selected supplier{picks.length === 1 ? "" : "s"}</p>
      <Button type="button" variant="primary" disabled={busy || uncertain || !picks.length} onClick={() => void approveFor2mg()}>Approve selected for 2MG</Button>
      {!!picks.length && <Button type="button" disabled={busy} onClick={() => setSelected({})}>Clear selection</Button>}
    </div>}
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
    <div className="flex flex-wrap items-center justify-between gap-3 text-meta text-ink-2">
      <p className="tabular-nums">{list.total} matching suppliers · Page {list.page} of {list.pages} ({list.items.length} shown)</p>
      <div className="flex flex-wrap gap-1.5">
        <Button size="sm" type="button" disabled={busy || uncertain || list.page <= 1} onClick={() => void load(1)}>First</Button>
        <Button size="sm" type="button" disabled={busy || uncertain || list.page <= 1} onClick={() => void load(list.page - 1)}>Previous</Button>
        <Button size="sm" type="button" disabled={busy || uncertain || list.page >= list.pages} onClick={() => void load(list.page + 1)}>Next</Button>
        <Button size="sm" type="button" disabled={busy || uncertain || list.page >= list.pages} onClick={() => void load(list.pages)}>Last</Button>
      </div>
    </div>
    <div role="region" aria-label="Suppliers list" tabIndex={0} className="max-h-[60vh] max-w-full overflow-auto overscroll-contain rounded-xl border border-rule bg-sheet shadow-sheet focus-visible:outline-2 focus-visible:outline-hema" aria-busy={busy}>
      <table className="w-full min-w-[52rem] text-sm"><caption className="sr-only">Suppliers with directly editable classification and usual withholding tax code</caption><thead className="sticky top-0 z-10 bg-sheet shadow-[0_1px_0_0_var(--color-rule)]"><tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
        {showSelection && <th className="w-10 py-3 pr-2 pl-4"><input type="checkbox" aria-label="Select suppliers on this page only" disabled={busy || uncertain || !list.items.length} checked={!!list.items.length && list.items.every(s => !!selected[s.id])} onChange={e => { const checked = e.target.checked; setSelected(previous => { const next = { ...previous }; for (const s of list.items) { if (checked) next[s.id] = s; else delete next[s.id]; } return next; }); }} /></th>}
        <th className="px-3 py-3 font-semibold first:pl-5">Supplier / contact</th><th className="px-3 py-3 font-semibold">Local / Foreign</th><th className="px-3 py-3 font-semibold">Usual tax withheld</th><th className="px-3 py-3 font-semibold">Tax defaults</th><th className="py-3 pr-5 pl-3 text-right font-semibold">Payables</th>
      </tr></thead><tbody className="divide-y divide-rule">{list.items.map(saved => {
        const row = edits[saved.id]?.after ?? saved;
        return <tr key={row.id} className={`transition-colors ${edits[row.id] ? "bg-bench/50" : "hover:bg-bench/30"}`}>
          {showSelection && <td className="py-3 pr-2 pl-4 align-top"><input type="checkbox" aria-label={`Select ${row.name}`} checked={!!selected[row.id]} disabled={busy || uncertain} onChange={e => { const checked = e.target.checked; setSelected(previous => { const next = { ...previous }; if (checked) next[row.id] = saved; else delete next[row.id]; return next; }); }} /></td>}
          <td className="px-3 py-3 first:pl-5"><Link className="font-semibold text-hema hover:underline" href={`/finance/suppliers/${row.id}`} onClick={e => { if (changes.length) { e.preventDefault(); setError("Save or discard your list changes before opening supplier details."); } }}>{row.name}</Link>{row.companyName && row.companyName !== row.name && <span className="block text-meta text-ink-2">{row.companyName}</span>}<span className="mt-0.5 block font-mono text-meta text-ink-3">{row.tin ? `TIN ${row.tin}${row.branchCode ? `-${row.branchCode}` : ""}` : "No TIN"}</span>{(row.email || row.phone) && <span className="block text-meta text-ink-3">{[row.email, row.phone].filter(Boolean).join(" · ")}</span>}{!row.isActive && <span className="block text-meta text-danger">Switched off</span>}{!!edits[row.id] && <span className="block text-meta font-semibold text-due-today">Unsaved change</span>}</td>
          <td className="px-3 py-3 align-middle">{list.canEdit ? <select aria-label={`${row.name}: Local or Foreign`} className={control} value={row.origin ?? ""} disabled={busy || uncertain} onChange={e => edit([saved], { origin: e.target.value as "local" | "foreign" })}><option value="" disabled>Not set</option><option value="local">Local</option><option value="foreign">Foreign</option></select> : where(row)}</td>
          <td className="px-3 py-3 align-middle">{list.canEdit ? <select aria-label={`${row.name}: usual tax withheld`} className={`${control} w-80`} value={row.withholding ?? ""} disabled={busy || uncertain} onChange={e => edit([saved], { withholding: e.target.value || null })}><option value="">No usual code</option>{list.withholding.map(w => <option key={w.code} value={w.code}>{w.code} · {w.name} · {w.rateBp / 100}%</option>)}</select> : codeLabel(row.withholding)}</td>
          <td className="px-3 py-3 align-middle text-meta">{edits[row.id] ? <span className="font-semibold text-due-today">Will need confirmation</span> : row.taxDefaultsConfirmed ? <span className="rounded-full bg-mint-2 px-2 py-0.5 font-medium text-sage-deep">Confirmed</span> : <span className="text-ink-3">Confirm on bill</span>}</td>
          <td className="py-3 pr-5 pl-3 align-middle text-right font-medium tabular-nums">{fmt.peso(row.owedCentavos)}</td>
        </tr>;
      })}{!list.items.length && <tr><td className="p-6 text-center text-ink-3" colSpan={showSelection ? 6 : 5}>No suppliers match these filters.</td></tr>}</tbody></table>
    </div>
    <div className="flex flex-wrap items-center justify-between gap-3 text-meta text-ink-2"><p className="tabular-nums">{list.total} matching suppliers · Page {list.page} of {list.pages} · {list.items.length} on this page</p><div className="flex flex-wrap gap-1.5"><Button size="sm" type="button" disabled={busy || uncertain || list.page <= 1} onClick={() => void load(1)}>First</Button><Button size="sm" type="button" disabled={busy || uncertain || list.page <= 1} onClick={() => void load(list.page - 1)}>Previous</Button><Button size="sm" type="button" disabled={busy || uncertain || list.page >= list.pages} onClick={() => void load(list.page + 1)}>Next</Button><Button size="sm" type="button" disabled={busy || uncertain || list.page >= list.pages} onClick={() => void load(list.pages)}>Last</Button></div></div>
  </div>;
}
