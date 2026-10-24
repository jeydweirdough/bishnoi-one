"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";
import type { MySignature } from "@/src/modules/finance/signature/types";

// Your e-signature (app/routers/profile.py), and an administrator removing someone's.

export async function setSignature(image: string, method: "drawn" | "uploaded", password: string | null): Promise<Result<MySignature>> {
  return attempt(async () => {
    const out = await api.put<MySignature>("/auth/signature", { image, method, password: password || null });
    refresh();
    return out;
  });
}

export async function removeSignature(password: string | null): Promise<Result<MySignature>> {
  return attempt(async () => {
    const out = await api.post<MySignature>("/auth/signature/remove", { password: password || null });
    refresh();
    return out;
  });
}

export async function removeUserSignature(userId: string): Promise<Result<null>> {
  return attempt(async () => {
    await api.del(`/admin/users/${enc(userId)}/signature`);
    refresh();
    return null;
  });
}
