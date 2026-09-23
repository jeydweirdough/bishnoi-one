"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { CompanySettings, CustomEntity, FormLayout } from "@/src/platform/lib/types";

// Settings: the forms, and company & quotes. The API checks admin.settings on
// each and logs every change.

/** A field as the form editor sends it back: `id` is empty for one added now. */
export type FieldDraft = {
  id: string | null;
  label: string;
  type: string;
  required: boolean;
  hidden: boolean;
  inList: boolean;
  options: string[];
  helpText: string | null;
  placeholder: string | null;
};
export type SectionDraft = { id: string | null; title: string; columns: 1 | 2; fields: FieldDraft[] };

/** The whole form, as laid out in the editor. Answers with the form as saved. */
export async function saveForm(entity: CustomEntity, sections: SectionDraft[]): Promise<Result<FormLayout>> {
  return attempt(async () => {
    const saved = await api.put<FormLayout>(`/admin/forms/${enc(entity)}`, { sections });
    refresh();
    return saved;
  });
}

export async function saveCompanySettings(change: Partial<Omit<CompanySettings, "currencies">>): Promise<Result<CompanySettings>> {
  return attempt(async () => {
    const saved = await api.patch<CompanySettings>("/admin/company-settings", change);
    refresh();
    return saved;
  });
}
