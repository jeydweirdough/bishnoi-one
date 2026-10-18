"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type {
  AdminUser,
  Batch,
  BatchStatus,
  Brand,
  Category,
  Dispensing,
  MaterialReviewDetail,
  Medicine,
  MedicineStatus,
  Movement,
  Patient,
  PaymentMethod,
  Prescription,
  PrescriptionStatus,
  Receiving,
  RoleRow,
  RxClass,
  Sale,
  SaleDetail,
  Supplier,
} from "../lib/types";

// Every change the Pharmacy's screens make. The API checks the caller's
// permission and every rule on each one (verified before dispensed, eligible
// batches only, no prescription medicine at the counter); these carry the
// request and hand back what it said.

const done = <T,>(value: T): T => {
  refresh();
  return value;
};

// --- medicines, categories, brands ---

export type MedicineInput = {
  code: string;
  genericName: string;
  brandId: string | null;
  categoryId: string | null;
  strength: string | null;
  dosageForm: string;
  unit: string;
  rxClass: RxClass;
  priceCentavos: number;
  reorderLevel: number;
  status: MedicineStatus;
  notes: string | null;
};

export async function createMedicine(input: MedicineInput): Promise<Result<Medicine>> {
  return attempt(async () => api.post<Medicine>("/medicines", input));
}

export async function updateMedicine(id: string, change: Partial<MedicineInput>): Promise<Result<Medicine>> {
  return attempt(async () => done(await api.patch<Medicine>(`/medicines/${enc(id)}`, change)));
}

export async function deleteMedicine(id: string): Promise<Result> {
  return attempt(async () => done(await api.del(`/medicines/${enc(id)}`)) ?? null);
}

export type NamedInput = { name: string; description?: string | null; manufacturer?: string | null; isActive: boolean };

export async function saveCategory(id: string | null, input: NamedInput): Promise<Result<Category>> {
  const body = { name: input.name, description: input.description ?? null, isActive: input.isActive };
  return attempt(async () =>
    done(id ? await api.put<Category>(`/medicines/categories/${enc(id)}`, body) : await api.post<Category>("/medicines/categories", body)),
  );
}

export async function deleteCategory(id: string): Promise<Result> {
  return attempt(async () => done(await api.del(`/medicines/categories/${enc(id)}`)) ?? null);
}

export async function saveBrand(id: string | null, input: NamedInput): Promise<Result<Brand>> {
  const body = { name: input.name, manufacturer: input.manufacturer ?? null, isActive: input.isActive };
  return attempt(async () =>
    done(id ? await api.put<Brand>(`/medicines/brands/${enc(id)}`, body) : await api.post<Brand>("/medicines/brands", body)),
  );
}

export async function deleteBrand(id: string): Promise<Result> {
  return attempt(async () => done(await api.del(`/medicines/brands/${enc(id)}`)) ?? null);
}

// --- patients and customers ---

export type PatientInput = {
  kind: "patient" | "customer";
  fullName: string;
  birthDate: string | null;
  sex: "female" | "male" | "other" | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  allergies: string | null;
  notes: string | null;
};

export async function createPatient(input: PatientInput): Promise<Result<Patient>> {
  return attempt(async () => api.post<Patient>("/patients", input));
}

export async function updatePatient(id: string, change: Partial<PatientInput>): Promise<Result<Patient>> {
  return attempt(async () => done(await api.patch<Patient>(`/patients/${enc(id)}`, change)));
}

export async function deletePatient(id: string): Promise<Result> {
  return attempt(async () => done(await api.del(`/patients/${enc(id)}`)) ?? null);
}

// --- prescriptions ---

export type ItemInput = { writtenAs: string; medicineId: string | null; quantity: number; directions: string | null };

export type PrescriptionInput = {
  patientId: string | null;
  newPatient: { fullName: string; birthDate: string | null; phone: string | null; allergies: string | null } | null;
  prescriberName: string;
  prescriberLicense: string | null;
  prescriberClinic: string | null;
  prescribedOn: string;
  notes: string | null;
  items: ItemInput[];
};

export async function receivePrescription(input: PrescriptionInput): Promise<Result<Prescription>> {
  return attempt(async () => api.post<Prescription>("/prescriptions", input));
}

export async function updatePrescription(id: string, change: Partial<Omit<PrescriptionInput, "patientId" | "newPatient">>): Promise<Result<Prescription>> {
  return attempt(async () => done(await api.patch<Prescription>(`/prescriptions/${enc(id)}`, change)));
}

export type CheckInput = {
  checks: Record<string, boolean>;
  matches: { itemId: string; medicineId: string | null }[];
  status: Exclude<PrescriptionStatus, "received">;
  notes: string | null;
};

export async function checkPrescription(id: string, input: CheckInput): Promise<Result<Prescription>> {
  return attempt(async () => done(await api.post<Prescription>(`/prescriptions/${enc(id)}/check`, input)));
}

// --- dispensing and sales ---

export type DispenseInput = {
  prescriptionId: string;
  lines: { itemId: string; batchId: string; quantity: number }[];
  paymentMethod: PaymentMethod;
  discountCentavos: number;
  notes: string | null;
};

export async function dispense(input: DispenseInput): Promise<Result<Dispensing>> {
  return attempt(async () => api.post<Dispensing>("/dispensing", input));
}

export type CounterSaleInput = {
  patientId: string | null;
  lines: { medicineId: string; quantity: number }[];
  paymentMethod: PaymentMethod;
  discountCentavos: number;
  notes: string | null;
};

export async function counterSale(input: CounterSaleInput): Promise<Result<Sale>> {
  return attempt(async () => api.post<Sale>("/sales", input));
}

export type ReturnInput = {
  lines: { saleLineId: string; quantity: number }[];
  reason: string;
  restock: boolean;
  refundCentavos: number;
  refundMethod: PaymentMethod | null;
};

export async function makeReturn(saleId: string, input: ReturnInput): Promise<Result<SaleDetail>> {
  return attempt(async () => done(await api.post<SaleDetail>(`/sales/${enc(saleId)}/returns`, input)));
}

// --- batches and stock ---

export async function setBatchStatus(id: string, status: BatchStatus, reason: string | null): Promise<Result<Batch>> {
  return attempt(async () => done(await api.post<Batch>(`/batches/${enc(id)}/status`, { status, reason })));
}

export type ReceivingInput = {
  supplierId: string | null;
  reference: string | null;
  receivedOn: string;
  notes: string | null;
  lines: { medicineId: string; lotNo: string; expiresOn: string; manufacturedOn: string | null; quantity: number; costCentavos: number }[];
};

export async function receiveStock(input: ReceivingInput): Promise<Result<Receiving>> {
  return attempt(async () => api.post<Receiving>("/stock/receivings", input));
}

export async function adjustStock(batchId: string, quantity: number, reason: string): Promise<Result<Movement>> {
  return attempt(async () => done(await api.post<Movement>("/stock/adjustments", { batchId, quantity, reason })));
}

// --- suppliers ---

export type SupplierInput = {
  name: string;
  contactPerson: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  notes: string | null;
  isActive: boolean;
};

export async function createSupplier(input: SupplierInput): Promise<Result<Supplier>> {
  return attempt(async () => api.post<Supplier>("/suppliers", input));
}

export async function updateSupplier(id: string, change: Partial<SupplierInput>): Promise<Result<Supplier>> {
  return attempt(async () => done(await api.patch<Supplier>(`/suppliers/${enc(id)}`, change)));
}

export async function deleteSupplier(id: string): Promise<Result> {
  return attempt(async () => done(await api.del(`/suppliers/${enc(id)}`)) ?? null);
}

// --- administration ---

export type UserInput = { email: string; fullName: string; roleId: string; licenseNo: string | null; password: string };
export type UserChange = Partial<Omit<UserInput, "password"> & { isActive: boolean }>;

export async function createUser(input: UserInput): Promise<Result<AdminUser>> {
  return attempt(async () => done(await api.post<AdminUser>("/admin/users", input)));
}

export async function updateUser(id: string, change: UserChange): Promise<Result<AdminUser>> {
  return attempt(async () => done(await api.patch<AdminUser>(`/admin/users/${enc(id)}`, change)));
}

export async function resetPassword(id: string, password: string): Promise<Result> {
  return attempt(async () => {
    await api.post(`/admin/users/${enc(id)}/password`, { password });
    return null;
  });
}

export type RoleInput = { name: string; description: string | null; permissions: string[] };

export async function createRole(input: RoleInput): Promise<Result<RoleRow>> {
  return attempt(async () => done(await api.post<RoleRow>("/admin/roles", input)));
}

export async function updateRole(id: string, change: Partial<RoleInput>): Promise<Result<RoleRow>> {
  return attempt(async () => done(await api.patch<RoleRow>(`/admin/roles/${enc(id)}`, change)));
}

export async function deleteRole(id: string): Promise<Result> {
  return attempt(async () => done(await api.del(`/admin/roles/${enc(id)}`)) ?? null);
}

// --- promotional material reviews ---

export type MaterialDecision = { outcome: "approved" | "returned" | "rejected"; comments: string | null };

export async function decideMaterial(id: string, input: MaterialDecision): Promise<Result<MaterialReviewDetail>> {
  return attempt(async () => done(await api.post<MaterialReviewDetail>(`/material-reviews/${enc(id)}/decision`, input)));
}
