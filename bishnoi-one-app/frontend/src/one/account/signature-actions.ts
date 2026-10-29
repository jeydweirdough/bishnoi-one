"use server";

import { revalidatePath } from "next/cache";
import { accountSend } from "@/src/platform/lib/account";
import { attempt, type Result } from "@/src/platform/lib/result";

// Your one e-signature, on your Bishnoi One account (feature plan step 10, /identity/signature). Every app
// uses it when you sign a step there.

export type PlatformSignature = { has: boolean; image: string | null; method: string | null; setAt: string | null };

export async function saveMySignature(image: string, method: "drawn" | "uploaded", password: string | null): Promise<Result<PlatformSignature>> {
  return attempt(async () => {
    const out = await accountSend<PlatformSignature>("PUT", "/identity/signature", { image, method, password: password ?? "" });
    revalidatePath("/platform/account");
    return out;
  });
}

export async function removeMySignature(password: string | null): Promise<Result<PlatformSignature>> {
  return attempt(async () => {
    const out = await accountSend<PlatformSignature>("POST", "/identity/signature/remove", { password: password ?? "" });
    revalidatePath("/platform/account");
    return out;
  });
}
