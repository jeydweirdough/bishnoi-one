"use server";

import { revalidatePath } from "next/cache";
import { accountSend } from "@/src/platform/lib/account";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Slip } from "./types";

// Signing, returning and adding files to an approval slip (Step 4C), on Bishnoi One Platform. The Platform
// decides whose turn it is; the record's app hears the slip's end.

const enc = encodeURIComponent;

function refresh(slip: Slip) {
  revalidatePath("/approvals");
  revalidatePath(`/approvals/${slip.id}`);
  if (slip.record.url) revalidatePath(slip.record.url);
}

export async function signSlip(id: string, note: string): Promise<Result<Slip>> {
  return attempt(async () => {
    const slip = await accountSend<Slip>("POST", `/identity/approvals/${enc(id)}/sign`, { note: note.trim() || null });
    refresh(slip);
    return slip;
  });
}

export async function returnSlip(id: string, note: string): Promise<Result<Slip>> {
  return attempt(async () => {
    const slip = await accountSend<Slip>("POST", `/identity/approvals/${enc(id)}/return`, { note: note.trim() });
    refresh(slip);
    return slip;
  });
}

export async function addSlipFile(id: string, form: FormData): Promise<Result<Slip>> {
  return attempt(async () => {
    const slip = await accountSend<Slip>("POST", `/identity/approvals/${enc(id)}/files`, form);
    refresh(slip);
    return slip;
  });
}
