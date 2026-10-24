"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { CodeFields, QuoteTemplate, TemplateDesign } from "@/src/modules/crm/quote-templates/types";

// Settings -> Quotation templates. The API checks that the caller manages settings.

export type TemplateInput = Partial<{
  name: string;
  kind: "form" | "excel" | "code";
  payer: string | null;
  teamId: string | null;
  isActive: boolean;
  controlPrefix: string | null;
  controlNext: number;
  controlDigits: number;
  design: Partial<TemplateDesign>;
  excelSheet: string;
}>;

export async function createTemplate(input: TemplateInput): Promise<Result<QuoteTemplate>> {
  return attempt(() => api.post<QuoteTemplate>("/admin/quote-templates", input));
}

export async function saveTemplate(id: string, input: TemplateInput): Promise<Result<QuoteTemplate>> {
  return attempt(async () => {
    const saved = await api.patch<QuoteTemplate>(`/admin/quote-templates/${enc(id)}`, input);
    refresh();
    return saved;
  });
}

export async function deleteTemplate(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/quote-templates/${enc(id)}`);
    refresh();
    return null;
  });
}

/** A logo or signature (a PNG from the drawing pad, or a file), or the Excel form. */
export async function uploadTemplateFile(id: string, part: "logo" | "signature" | "excel", form: FormData): Promise<Result<QuoteTemplate>> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) return { ok: false, error: "Choose a file first." };
  const body = new FormData();
  body.set("file", file, file.name);
  const path = part === "excel" ? `/admin/quote-templates/${enc(id)}/excel` : `/admin/quote-templates/${enc(id)}/images/${part}`;
  return attempt(async () => {
    const saved = await api.upload<QuoteTemplate>(path, body);
    refresh();
    return saved;
  });
}

export async function removeTemplateImage(id: string, which: "logo" | "signature"): Promise<Result<QuoteTemplate>> {
  return attempt(async () => {
    const saved = await api.del<QuoteTemplate>(`/admin/quote-templates/${enc(id)}/images/${which}`);
    refresh();
    return saved;
  });
}

/** The %fields% a template written as code can use, and a layout to start from. */
export async function codeFields(): Promise<Result<CodeFields>> {
  return attempt(() => api.get<CodeFields>("/admin/quote-template-fields"));
}

/** The code as it would print, before it's saved: with the template's latest quote, or made-up values. */
export async function previewCode(id: string, html: string): Promise<Result<{ html: string; using: string }>> {
  return attempt(() => api.post<{ html: string; using: string }>(`/admin/quote-templates/${enc(id)}/preview`, { html }));
}
