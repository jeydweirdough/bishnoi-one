"use server";
import { revalidatePath } from "next/cache";
import { accountSend } from "@/src/platform/lib/account";
import { attempt } from "@/src/platform/lib/result";
import type { PolicyPreview, PolicyVersion } from "./policy-types";
const root = "/identity/access/policy";

export async function generatePolicyPrompt(requirements: string) {
  return attempt(() => accountSend<{ prompt: string }>("POST", `${root}/prompt`, { requirements }));
}
export async function validatePolicyResponse(response: string) {
  return attempt(() => accountSend<PolicyPreview>("POST", `${root}/validate`, { response }));
}
export async function applyPolicyPreview(id: string, confirmed: boolean) {
  return attempt(async () => {
    const result = await accountSend<{ id: string; roles: number; appliedAt: string }>("POST", `${root}/${encodeURIComponent(id)}/apply`, { confirmed });
    revalidatePath("/platform", "layout");
    return result;
  });
}
export async function exportAccessPolicy() {
  return attempt(() => accountSend<Record<string, unknown>>("GET", `${root}/export`));
}
export async function downloadPolicyVersion(id: string) {
  return attempt(() => accountSend<Record<string, unknown>>("GET", `${root}/history/${encodeURIComponent(id)}`));
}
export async function refreshPolicyHistory() {
  return attempt(() => accountSend<PolicyVersion[]>("GET", `${root}/history`));
}
