"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Voucher, VoucherChoices, VoucherMethod } from "./types";

// Payment vouchers. The API checks every step's rules: who may do it, that only bills ready to
// pay go on one, and that no bill is paid twice.

export type VoucherInput = {
  supplierId: string;
  method: VoucherMethod;
  paidFromId: string | null;
  oojeemaRef: string | null;
  zohoRef: string | null;
  notes: string | null;
  lines: { billId: string; amountCentavos: number }[];
};

/** A supplier's bills a voucher can pay (and what other open vouchers already set aside). */
export async function voucherChoices(supplierId: string, voucherId: string | null): Promise<Result<VoucherChoices>> {
  const query = new URLSearchParams({ supplier: supplierId });
  if (voucherId) query.set("voucher", voucherId);
  return attempt(() => api.get<VoucherChoices>(`/finance/vouchers/choices?${query}`));
}

export async function saveVoucher(id: string | null, input: VoucherInput): Promise<Result<Voucher>> {
  return attempt(async () => {
    const saved = id ? await api.put<Voucher>(`/finance/vouchers/${enc(id)}`, input) : await api.post<Voucher>("/finance/vouchers", input);
    refresh();
    return saved;
  });
}

/** One step: submit; return, cancel and void need a reason; release its details. */
export async function voucherStep(id: string, step: "submit" | "return" | "cancel" | "void" | "release", body: object = {}): Promise<Result<Voucher>> {
  return attempt(async () => {
    const saved = await api.post<Voucher>(`/finance/vouchers/${enc(id)}/${step}`, body);
    refresh();
    return saved;
  });
}

export async function attachVoucherFile(id: string, form: FormData): Promise<Result<Voucher>> {
  return attempt(async () => {
    const file = form.get("file");
    if (!(file instanceof File)) throw new Error("No file");
    const data = Buffer.from(await file.arrayBuffer()).toString("base64");
    const saved = await api.post<Voucher>(`/finance/vouchers/${enc(id)}/files`, { name: file.name, contentType: file.type, data });
    refresh();
    return saved;
  });
}

export async function removeVoucherFile(id: string, fileId: string): Promise<Result<Voucher>> {
  return attempt(async () => {
    const saved = await api.del<Voucher>(`/finance/vouchers/${enc(id)}/files/${enc(fileId)}`);
    refresh();
    return saved;
  });
}
