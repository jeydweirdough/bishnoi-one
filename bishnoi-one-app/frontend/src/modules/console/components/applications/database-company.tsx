"use client";
import { useState } from "react";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { updateApplication } from "@/src/modules/console/actions/applications";
import type { ApplicationDetail } from "@/src/modules/console/lib/types";

/** Select a known company; slugs/currency/timezone come from its Platform record. */
export function DatabaseCompany({ app, admin }: { app: ApplicationDetail; admin: boolean }) {
  const candidates = app.companies.filter(c => c.status === "active");
  const [selected, setSelected] = useState(app.databaseCompanyId ?? (candidates.length === 1 ? candidates[0].id : ""));
  const [error, setError] = useState<string | null>(null);
  const current = app.companies.find(c => c.id === app.databaseCompanyId);
  const wanted = candidates.find(c => c.id === selected);
  return <Sheet className="mb-5 space-y-3 px-5 py-4">
    <h2 className="text-heading">Database company</h2>
    <p className="text-sm text-ink-3">This Finance database contains one company&apos;s books. The selected company supplies its slug, currency and timezone to Finance automatically.</p>
    <p className="text-sm">{current?.status === "active" ? `Current company: ${current.name}.` : app.databaseCompanyId ? "The configured company is unavailable. Reads remain blocked until the correct company is selected." : candidates.length === 1 ? `${candidates[0].name} will be linked automatically when Finance connects.` : "Select the company whose data this Finance database contains."}</p>
    {admin && <>
      <Field label="Company" hint="Choose an existing active company with Finance access.">{field => <select {...field} value={selected} onChange={event => { setSelected(event.target.value); setError(null); }} className="h-10 w-full rounded-lg border border-rule bg-sheet px-3 text-sm"><option value="">Select a company</option>{candidates.map(company => <option key={company.id} value={company.id}>{company.name}</option>)}</select>}</Field>
      <ConfirmButton label="Save database company" title="Confirm Finance database company" confirmLabel="Save company" danger={Boolean(app.databaseCompanyId)} disabled={!wanted || selected === app.databaseCompanyId}
        body={<p>Confirm that this Finance database contains <strong>{wanted?.name}</strong>&apos;s books. This controls which company may read them. This setting does not move or convert any financial records.</p>}
        onConfirm={async () => {
          const result = await updateApplication(app.id, { databaseCompanyId: selected });
          if (!result.ok) { setError(result.error); return false; }
          setError(null); toast.success("Database company saved");
        }} />
      <FormError message={error} />
    </>}
  </Sheet>;
}
