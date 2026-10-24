"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { CompanySettings, CustomEntity, FormLayout } from "@/src/platform/lib/types";
import type { Terms } from "@/src/modules/crm/components/terms/terms";

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
  optionNames: Record<string, string>;
  unique: boolean;
  onlyTeams: string[];
  onlyTypes: string[];
  exceptTypes: string[];
  exceptTeams: string[];
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

/** One more choice on a pick-list, from the form it's missing from. Answers with the choice as kept. */
export async function addChoice(entity: CustomEntity, key: string, label: string): Promise<Result<{ option: string }>> {
  return attempt(async () => {
    const added = await api.post<{ option: string }>(`/admin/forms/${enc(entity)}/fields/${enc(key)}/options`, { label });
    refresh();
    return { option: added.option };
  });
}

// --- connections to outside services (Settings → Connections) ---

/** Which services the CRM can use for this company: they're connected on Bishnoi One Platform. */
export type Connections = {
  /** Whether the CRM has its connect key, so it can ask the platform at all. */
  connected: boolean;
  company: string | null;
  services: { key: string; name: string; purpose: string; on: boolean }[];
};

// --- Settings → Attention: when something is worth a prompt on the home page ---

export type Rule = { team: { id: string; name: string } | null; quietDays: number; noticeDays: number; clidpDays: number; stuckDays: number };
/** canSetEveryone: false for a manager, who sets only their own divisions'. */
export type AttentionRules = { everyone: Rule; divisions: Rule[]; teams: { id: string; name: string }[]; canSetEveryone?: boolean };

export async function saveAttentionRule(rule: { teamId: string | null; quietDays: number; noticeDays: number; clidpDays: number; stuckDays: number }): Promise<Result<AttentionRules>> {
  return attempt(() => api.put<AttentionRules>("/admin/attention-rules", rule));
}

/** A division goes back to everyone's rule. */
export async function dropAttentionRule(teamId: string): Promise<Result<AttentionRules>> {
  return attempt(() => api.del<AttentionRules>(`/admin/attention-rules/${enc(teamId)}`));
}

// --- Settings → Associations: what a link between two records can mean ---

export type AssociationLabel = { code: string; fromType: string; toType: string; name: string; inverseName: string; isActive: boolean; used: number };

export async function addAssociationLabel(label: { fromType: string; toType: string; name: string; inverseName: string }): Promise<Result<AssociationLabel[]>> {
  return attempt(() => api.post<AssociationLabel[]>("/admin/association-labels", label));
}

export async function changeAssociationLabel(code: string, change: Partial<{ name: string; inverseName: string; isActive: boolean }>): Promise<Result<AssociationLabel[]>> {
  return attempt(() => api.patch<AssociationLabel[]>(`/admin/association-labels/${enc(code)}`, change));
}

/** The company's own words (Settings → Terms), saved whole. */
export type TermsSettings = {
  terms: Terms;
  general: Terms;
  pharma: Terms;
  customerTypes: { code: string; name: string }[];
};

export async function saveTerms(terms: Terms): Promise<Result<TermsSettings>> {
  return attempt(async () => {
    const saved = await api.put<TermsSettings>("/admin/terms", terms);
    refresh();
    return saved;
  });
}

// --- Settings → Retention windows: when a department's customers are at risk, and lost ---

export type Window = { atRiskDays: number; lostDays: number };
/** own: the department keeps its own windows; else it uses the company's. */
export type RetentionWindows = { company: Window; teams: { id: string; name: string; atRiskDays: number | null; lostDays: number | null; own: boolean }[] };

/** A department's own windows, or (both null) back to the company's. */
export async function saveRetentionWindows(teamId: string, w: { atRiskDays: number | null; lostDays: number | null }): Promise<Result<RetentionWindows>> {
  return attempt(() => api.put<RetentionWindows>(`/retention/windows/${enc(teamId)}`, w));
}
