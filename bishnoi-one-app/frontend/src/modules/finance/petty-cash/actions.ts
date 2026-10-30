"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";
import type { PettyCashInput, PettyCashVoucher } from "@/src/modules/finance/petty-cash/types";

// Petty cash vouchers (app/routers/petty_cash.py). The API works each voucher out, checks the
// person's role for every step, and keeps whoever made or submitted it from checking it.

export async function savePettyCash(id: string | null, input: PettyCashInput): Promise<Result<PettyCashVoucher>> {
  return attempt(async () => {
    const saved = id ? await api.put<PettyCashVoucher>(`/finance/petty-cash/${enc(id)}`, input) : await api.post<PettyCashVoucher>("/finance/petty-cash", input);
    refresh();
    return saved;
  });
}

export async function deletePettyCash(id: string): Promise<Result<null>> {
  return attempt(async () => {
    await api.del(`/finance/petty-cash/${enc(id)}`);
    refresh();
    return null;
  });
}

/** One step: submit for checking; check and post; return (with the reason); void a posted one (with the reason). */
export async function pettyCashStep(id: string, step: "submit" | "check" | "return" | "void", body: object = {}): Promise<Result<PettyCashVoucher>> {
  return attempt(async () => {
    const saved = await api.post<PettyCashVoucher>(`/finance/petty-cash/${enc(id)}/${step}`, body);
    refresh();
    return saved;
  });
}

/** The photo or PDF of one receipt line: sent as the file itself, handed to the API as base64. Attaching again replaces it. */
export async function attachReceipt(id: string, lineId: string, form: FormData): Promise<Result<PettyCashVoucher>> {
  return attempt(async () => {
    const file = form.get("file");
    if (!(file instanceof File)) throw new Error("No file");
    const body = { name: file.name, contentType: file.type, data: Buffer.from(await file.arrayBuffer()).toString("base64") };
    const saved = await api.post<PettyCashVoucher>(`/finance/petty-cash/${enc(id)}/lines/${enc(lineId)}/file`, body);
    refresh();
    return saved;
  });
}

export async function removeReceipt(id: string, lineId: string): Promise<Result<PettyCashVoucher>> {
  return attempt(async () => {
    const saved = await api.del<PettyCashVoucher>(`/finance/petty-cash/${enc(id)}/lines/${enc(lineId)}/file`);
    refresh();
    return saved;
  });
}
