"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { QuoteTemplate, TemplateDesign } from "@/src/quote-templates/types";

// Settings -> Quotation templates. The API checks that the caller manages settings.

export type TemplateInput = Partial<{
  name: string;
  kind: "form" | "excel";
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
