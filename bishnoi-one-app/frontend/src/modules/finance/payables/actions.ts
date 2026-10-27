"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";
import type { SupplierRow } from "@/src/modules/finance/payables/csv";
import type { Bill, BillLineInput, Supplier, SupplierContact, SupplierImportCheck } from "@/src/modules/finance/payables/types";

// Suppliers and bills. The API works each bill out, posts it once it's approved (and checked), and
// checks the person's role for every step (app/routers/payables.py).

export type SupplierInput = {
  taxDefaultsConfirmed?: boolean;
  name: string;
  companyName: string | null;
  salutation: string | null;
  firstName: string | null;
  lastName: string | null;
  mobile: string | null;
  payablesAccountId: string | null;
  contacts: SupplierContact[];
  tin: string | null;
  branchCode: string | null;
  address: string | null;
  vatRegistered: boolean;
  withholding: string | null;
  termsDays: number;
  email: string | null;
  phone: string | null;
  bankName: string | null;
  bankAccountName: string | null;
  bankAccountNumber: string | null;
  notes: string | null;
};

/** Suppliers read from Zoho's vendor export in the browser, checked by the API: nothing is added yet. */
export async function checkSupplierImport(rows: SupplierRow[]): Promise<Result<SupplierImportCheck>> {
  return attempt(() => api.post<SupplierImportCheck>("/finance/suppliers/import/check", { rows }));
}

/** The chosen suppliers, added all or none. */
export async function importSuppliers(rows: SupplierRow[]): Promise<Result<{ added: number }>> {
  return attempt(async () => {
    const done = await api.post<{ added: number }>("/finance/suppliers/import", { rows, confirmed: true });
    refresh();
    return done;
  });
}

/** Switching a supplier off (not offered on new bills) or back on: its own tick, suppliers.deactivate. */
export async function switchSupplier(id: string, isActive: boolean): Promise<Result<Supplier>> {
  return attempt(async () => {
    const saved = await api.post<Supplier>(`/finance/suppliers/${enc(id)}/active`, { isActive });
    refresh();
    return saved;
  });
}

/** A supplier's papers (BIR 2303, accreditation), attached like a bill's invoice. */
export async function attachSupplierFile(id: string, form: FormData): Promise<Result<Supplier>> {
  return attempt(async () => {
    const saved = await api.post<Supplier>(`/finance/suppliers/${enc(id)}/files`, await asFile(form));
    refresh();
    return saved;
  });
}

export async function removeSupplierFile(id: string, fileId: string): Promise<Result<Supplier>> {
  return attempt(async () => {
    const saved = await api.del<Supplier>(`/finance/suppliers/${enc(id)}/files/${enc(fileId)}`);
    refresh();
    return saved;
  });
}

/** The picked file, as the API takes it: its name, type, and the bytes as base64. */
async function asFile(form: FormData): Promise<{ name: string; contentType: string; data: string }> {
  const file = form.get("file");
  if (!(file instanceof File)) throw new Error("No file");
  return { name: file.name, contentType: file.type, data: Buffer.from(await file.arrayBuffer()).toString("base64") };
}

export async function saveSupplier(id: string | null, input: SupplierInput): Promise<Result<Supplier>> {
  return attempt(async () => {
    const saved = id ? await api.put<Supplier>(`/finance/suppliers/${enc(id)}`, input) : await api.post<Supplier>("/finance/suppliers", input);
    refresh();
    return saved;
  });
}

export type BillInput = {
  taxReviewed: boolean;
  saveSupplierDefaults?: boolean;
  supplierVatRegistered?: boolean | null;
  supplierWithholding?: string | null;
  supplierId: string;
  billNumber: string;
  billDate: string;
  dueDate: string | null;
  poNumber: string | null;
  drNumber: string | null;
  checkedPo: boolean;
  checkedDr: boolean;
  amountsIncludeVat: boolean;
  zohoRef: string | null;
  oojeemaRef: string | null;
  notes: string | null;
  lines: BillLineInput[];
};

export async function saveBill(id: string | null, input: BillInput): Promise<Result<Bill>> {
  return attempt(async () => {
    const saved = id ? await api.put<Bill>(`/finance/bills/${enc(id)}`, input) : await api.post<Bill>("/finance/bills", input);
    refresh();
    return saved;
  });
}

export async function deleteBill(id: string): Promise<Result<null>> {
  return attempt(async () => {
    await api.del(`/finance/bills/${enc(id)}`);
    refresh();
    return null;
  });
}

/** One step of a bill's approval: submit, approve, check; return needs a reason. Posting happens
 *  in the API when the bill clears. */
export async function billStep(id: string, step: "submit" | "approve" | "check" | "return", body: object = {}): Promise<Result<Bill>> {
  return attempt(async () => {
    const saved = await api.post<Bill>(`/finance/bills/${enc(id)}/${step}`, body);
    refresh();
    return saved;
  });
}

export async function voidBill(id: string, reason: string): Promise<Result<Bill>> {
  return attempt(async () => {
    const saved = await api.post<Bill>(`/finance/bills/${enc(id)}/void`, { reason });
    refresh();
    return saved;
  });
}

/** The supplier's invoice, attached: sent as the file itself (not text), then handed to the
 *  API as base64. Photos are made smaller in the browser first (src/payables/shrink.ts). */
export async function attachFile(id: string, form: FormData): Promise<Result<Bill>> {
  return attempt(async () => {
    const saved = await api.post<Bill>(`/finance/bills/${enc(id)}/files`, await asFile(form));
    refresh();
    return saved;
  });
}

export async function removeFile(id: string, fileId: string): Promise<Result<Bill>> {
  return attempt(async () => {
    const saved = await api.del<Bill>(`/finance/bills/${enc(id)}/files/${enc(fileId)}`);
    refresh();
    return saved;
  });
}
