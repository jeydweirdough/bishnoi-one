"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { saveCompany, type CompanyInput } from "../actions/admin";
import type { Company } from "@/src/platform/lib/types";
import { SaveBar } from "@/src/platform/ui/pick-list";

// Settings → Company: who this company is. How it writes money, dates and
// times is a rule about how figures read rather than part of its identity, so
// that lives on its own screen (Settings → Money & formats).

type Draft = { name: string; brandName: string };

function toDraft(c: Company): Draft {
  return { name: c.name, brandName: c.brandName };
}

export function CompanySettings({ data }: { data: Company }) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(data));
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();

  const saved = toDraft(data);
  const changed = (Object.keys(saved) as (keyof Draft)[]).filter((k) => draft[k].trim() !== saved[k]);
  const change = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch });

  function save() {
    const found: Record<string, string> = {};
    if (draft.name.trim().length < 2) found.name = "Name it, in 2 letters or more.";
    if (draft.brandName.trim().length < 1) found.brandName = "The short name every screen shows.";
    setProblems(found);
    if (Object.keys(found).length) return setError("Some fields need a look.");

    // Only what they touched travels: a PATCH that mentions a field sets it.
    const sent = (key: keyof Draft) => (changed.includes(key) ? draft[key].trim() : undefined);
    const input: CompanyInput = { name: sent("name"), brandName: sent("brandName") };
    start(async () => {
      const result = await saveCompany(input);
      if (!result.ok) {
        setProblems(result.fields ?? {});
        return setError(result.error);
      }
      setError(null);
      toast.success("Company saved", { description: "Every screen shows the new name from now on." });
    });
  }

  return (
    <>
      <Sheet className="max-w-[40rem] px-5 pt-4 pb-5">
        <SectionTitle icon="company">Who you are</SectionTitle>
        <div className="mt-3 space-y-5">
          <Field label="Name" error={problems.name} hint="The company's full legal name, for letters and reports.">
            {(p) => <Input {...p} value={draft.name} maxLength={120} onChange={(e) => change({ name: e.target.value })} />}
          </Field>
          <Field label="Short name" error={problems.brandName} hint="What the top of every screen says, above Orbit's own name.">
            {(p) => (
              <Input {...p} value={draft.brandName} maxLength={80} onChange={(e) => change({ brandName: e.target.value })} className="max-w-xs" />
            )}
          </Field>
          <div className="border-t border-rule pt-4">
            <Particulars items={[["Address in Orbit", <span key="slug" className="font-medium">{data.slug}</span>]]} />
            <p className="mt-2.5 text-meta text-ink-3">That one can&apos;t change: other things already point at it.</p>
          </div>
        </div>
      </Sheet>

      {changed.length > 0 && (
        <SaveBar
          what={`Unsaved changes to ${saved.name}`}
          saving={saving}
          onSave={save}
          onDiscard={() => {
            setDraft(saved);
            setProblems({});
            setError(null);
          }}
          error={<FormError message={error} />}
        />
      )}
    </>
  );
}
