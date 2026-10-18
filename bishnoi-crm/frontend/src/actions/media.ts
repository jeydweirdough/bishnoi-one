"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// Media: approved materials. Administrators add and change them (the API
// checks admin.settings); everyone opens what's current for their division.

export type Material = {
  id: string;
  title: string;
  description: string | null;
  kind: "file" | "link";
  fileName: string | null;
  products: { code: string; name: string }[];
  onlyTeams: string[];
  approvedOn: string;
  expiresOn: string | null;
  isActive: boolean;
  isCurrent: boolean;
  /** For administrators only. */
  opened30d?: number;
  url?: string | null;
};

export type MaterialInput = {
  title: string;
  description: string | null;
  url: string | null;
  products: string[];
  onlyTeams: string[];
  approvedOn: string;
  expiresOn: string | null;
};

/** Adds one: with a link, or (when `form` carries a file) with the file uploaded after. */
export async function saveMaterial(id: string | null, input: MaterialInput, form: FormData | null): Promise<Result<Material>> {
  return attempt(async () => {
    let item = id ? await api.patch<Material>(`/admin/media/${enc(id)}`, input) : await api.post<Material>("/admin/media", input);
    const file = form?.get("file");
    if (file instanceof File && file.size > 0) {
      const body = new FormData();
      body.set("file", file, file.name);
      item = await api.upload<Material>(`/admin/media/${enc(item.id)}/file`, body, "PUT");
    }
    refresh();
    return item;
  });
}

export async function switchMaterial(id: string, isActive: boolean): Promise<Result<Material>> {
  return attempt(async () => {
    const item = await api.patch<Material>(`/admin/media/${enc(id)}`, { isActive });
    refresh();
    return item;
  });
}

export async function deleteMaterial(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/media/${enc(id)}`);
    refresh();
    return null;
  });
}

/** Counts an opening (for the customer, when there is one) and answers where it is. */
export async function openMaterial(id: string, companyId: string | null): Promise<Result<{ url: string | null; file: boolean }>> {
  return attempt(() => api.post<{ url: string | null; file: boolean }>(`/media/${enc(id)}/opened`, { companyId }));
}
