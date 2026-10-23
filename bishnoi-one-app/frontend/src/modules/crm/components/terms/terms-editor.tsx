"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { saveTerms, type TermsSettings } from "@/src/modules/crm/actions/settings";
import type { Terms } from "@/src/modules/crm/components/terms/terms";

/** The company's words, with where each one shows, and two starting points. */
export function TermsEditor({ data }: { data: TermsSettings }) {
  const [draft, setDraft] = useState<Terms>(data.terms);
  const [errors, setErrors] = useState<{ error?: string; fields?: Record<string, string> }>({});
  const [pending, start] = useTransition();
  const set = (patch: Partial<Terms>) => setDraft((d) => ({ ...d, ...patch }));
  const same = JSON.stringify(draft) === JSON.stringify(data.terms);
  const one = draft.visited.one.trim().toLowerCase() || "account";
  const many = draft.visited.many.trim() || "Accounts";
  const site = draft.site.trim().toLowerCase() || "location";

  function save() {
    start(async () => {
      const result = await saveTerms({
        ...draft,
        visited: { one: draft.visited.one.trim(), many: draft.visited.many.trim() },
        detailing: draft.detailing.trim(),
        site: draft.site.trim(),
        genericName: draft.genericName.trim(),
      });
      if (!result.ok) {
        setErrors({ error: result.fields ? undefined : result.error, fields: result.fields });
        return;
      }
      setErrors({});
      setDraft(result.data.terms);
      toast.success("Terms saved", { description: "Every screen uses them from now on." });
    });
  }

  const pharma = () =>
    set({ ...data.pharma, visitedType: data.customerTypes.some((t) => t.code === data.pharma.visitedType) ? data.pharma.visitedType : null });

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="particulars">Terms</SectionTitle>
        <div className="mt-4 grid gap-5 sm:grid-cols-2">
          <Field label="Visited account (singular)" hint="On visits: Doctor, Account, Store." error={errors.fields?.["visited.one"]}>
            {(p) => <Input {...p} value={draft.visited.one} maxLength={40} onChange={(e) => set({ visited: { ...draft.visited, one: e.target.value } })} />}
          </Field>
          <Field label="Visited account (plural)" hint="In the menu: Field work → Doctors, Accounts, Stores." error={errors.fields?.["visited.many"]}>
            {(p) => <Input {...p} value={draft.visited.many} maxLength={40} onChange={(e) => set({ visited: { ...draft.visited, many: e.target.value } })} />}
          </Field>
          <Field label="Customer type" hint={`The customer type listed under ${many}. Any customer, if none is picked.`} error={errors.fields?.visitedType}>
            {(p) => (
              <Select {...p} value={draft.visitedType ?? ""} onChange={(e) => set({ visitedType: e.target.value || null })}>
                <option value="">Any customer</option>
                {data.customerTypes.map((t) => (
                  <option key={t.code} value={t.code}>
                    {t.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Visit location" hint={`"Logged away from the ${site}", and the place's pin.`} error={errors.fields?.site}>
            {(p) => <Input {...p} value={draft.site} maxLength={40} onChange={(e) => set({ site: e.target.value })} />}
          </Field>
          <Field label="Product detailing" hint="The heading over the products discussed on visits." error={errors.fields?.detailing}>
            {(p) => <Input {...p} value={draft.detailing} maxLength={60} onChange={(e) => set({ detailing: e.target.value })} />}
          </Field>
          <Field label="Generic name" hint="The kind of form field that offers it." error={errors.fields?.genericName}>
            {(p) => <Input {...p} value={draft.genericName} maxLength={40} onChange={(e) => set({ genericName: e.target.value })} />}
          </Field>
        </div>
        <p className="mt-5 rounded-lg bg-mint px-4 py-3 text-meta text-ink-2">
          Reads as: “Select the {one} response” · “{many} visited” · “At the {site}”
        </p>
        <FormError message={errors.error} />
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="quiet" onClick={() => setDraft(data.terms)} disabled={same || pending}>
            Undo changes
          </Button>
          <Button variant="primary" onClick={save} loading={pending} disabled={same}>
            Save terms
          </Button>
        </div>
      </Sheet>

      <Sheet className="h-fit px-5 pt-4 pb-5">
        <SectionTitle>Start from</SectionTitle>
        <p className="mt-1 text-meta text-ink-3">Fills the words in; nothing changes until you save.</p>
        <div className="mt-4 space-y-2">
          <Button className="w-full" onClick={() => set(data.general)}>
            General words
          </Button>
          <Button className="w-full" onClick={pharma}>
            A pharmaceutical company
          </Button>
        </div>
        <p className="mt-4 text-meta text-ink-3">General: accounts, location, product presentation, product family. Pharmaceutical: doctors, clinic, detailing, molecule.</p>
      </Sheet>
    </div>
  );
}
