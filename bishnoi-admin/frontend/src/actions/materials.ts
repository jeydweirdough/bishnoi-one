"use server";

// Promotional materials (app/routers/materials.py): the marketing assistant's
// designs, the pharmacist's review in Pharmacy, the executive office's
// production, and giving them out with the CRM manager's approval. The API
// checks each permission.

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

export type MaterialStatus = "draft" | "pharmacy_review" | "returned" | "rejected" | "approved" | "in_production" | "available" | "retired";
export type Review = "draft" | "waiting" | "approved" | "returned" | "rejected";

export type Material = {
  id: string;
  no: number | null;
  title: string;
  kind: string;
  product: string | null;
  description: string | null;
  quantity: number | null;
  specs: string | null;
  neededBy: string | null;
  budget: number | null;
  status: MaterialStatus;
  stock: number;
  reserved: number;
  available: number;
  version: number | null;
  review: Review | null;
  createdBy: string | null;
  createdAt: string;
  updatedAt: string;
  urgency: Urgency;
};

/** What makes it pressing, from its own dates and stock (never a made-up deadline). */
export type Urgency = {
  /** Days until it's needed, while it isn't in stock yet; below zero, late. */
  neededIn: number | null;
  tier: "overdue" | "urgent" | "approaching" | "upcoming" | "good_standing" | "none";
  waiting: { on: "pharmacist" | "manager"; days: number } | null;
  lowStock: boolean;
  /** The step that moves it on, with its timing. */
  next: string | null;
  /** The same step without its timing, where a countdown sits beside it. */
  step: string | null;
};

export type Version = {
  number: number;
  fileName: string | null;
  hasFile: boolean;
  notes: string | null;
  review: Review;
  sentAt: string | null;
  sentBy: string | null;
  pharmacyNumber: string | null;
  comments: string | null;
  reviewedBy: string | null;
  reviewedAt: string | null;
  syncedAt: string | null;
  syncError: string | null;
};

export type Production = {
  id: string;
  versionNumber: number;
  quantity: number;
  supplier: string | null;
  cost: number | null;
  orderedOn: string | null;
  expectedOn: string | null;
  receivedOn: string | null;
  status: "ordered" | "received" | "cancelled";
  notes: string | null;
  by: string | null;
  proof: Proof | null;
};

export type Distribution = {
  id: string;
  no: number | null;
  teamId: string;
  teamName: string;
  recipientId: string | null;
  recipientName: string | null;
  quantity: number;
  purpose: string | null;
  status: "for_approval" | "approved" | "rejected" | "distributed" | "cancelled";
  requestedBy: string | null;
  managerName: string | null;
  decisionNote: string | null;
  decidedAt: string | null;
  distributedOn: string | null;
  requestedAt: string;
  syncedAt: string | null;
  syncError: string | null;
  proof: Proof | null;
};

/** A photo or scan kept as proof: a delivery received, a hand-over. */
export type Proof = { ref: string; name: string };

export type MaterialPage = {
  material: Material;
  versions: Version[];
  productions: Production[];
  distributions: Distribution[];
  history: { id: string; kind: string; text: string; by: string | null; at: string }[];
  can: { edit: boolean; upload: boolean; submit: boolean; produce: boolean; distribute: boolean; recordDistribution: boolean; retire: boolean; delete: boolean };
  kinds: string[];
  linked: { pharmacy: boolean; crm: boolean };
};

export type CrmTeam = { id: string; name: string; manager: { id: string; name: string } | null; people: { id: string; name: string }[] };

export type MaterialInput = {
  title: string;
  kind: string;
  product: string | null;
  description: string | null;
  quantity: number | null;
  specs: string | null;
  neededBy: string | null;
  budget: number | null;
};

const base = (id: string) => `/admin/materials/${enc(id)}`;

async function step(path: string, body?: unknown): Promise<MaterialPage> {
  const out = await api.post<MaterialPage>(path, body ?? {});
  refresh();
  return out;
}

export async function saveMaterial(id: string | null, input: MaterialInput): Promise<Result<MaterialPage>> {
  return attempt(async () => {
    const out = id ? await api.patch<MaterialPage>(base(id), input) : await api.post<MaterialPage>("/admin/materials", input);
    refresh();
    return out;
  });
}

export async function deleteMaterial(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(base(id));
    refresh();
    return null;
  });
}

/** The design's file, with what changed for the pharmacist. */
export async function uploadDesign(id: string, form: FormData): Promise<Result<MaterialPage>> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) return { ok: false, error: "Choose the design's file first." };
  const body = new FormData();
  body.set("file", file, file.name);
  const notes = String(form.get("notes") ?? "").trim();
  if (notes) body.set("notes", notes);
  return attempt(async () => {
    const out = await api.upload<MaterialPage>(`${base(id)}/design`, body, "PUT");
    refresh();
    return out;
  });
}

export async function submitForReview(id: string): Promise<Result<MaterialPage>> {
  return attempt(() => step(`${base(id)}/submit`));
}

export async function checkAgain(id: string): Promise<Result<MaterialPage>> {
  return attempt(() => step(`${base(id)}/refresh`));
}

export async function retireMaterial(id: string): Promise<Result<MaterialPage>> {
  return attempt(() => step(`${base(id)}/retire`));
}

export type ProductionInput = { quantity: number; supplier: string | null; cost: number | null; orderedOn: string | null; expectedOn: string | null; notes: string | null };

export async function orderProduction(id: string, input: ProductionInput): Promise<Result<MaterialPage>> {
  return attempt(() => step(`${base(id)}/productions`, input));
}

/** The date it happened, and a photo or scan as proof when there is one. */
function withProof(field: string, form: FormData): FormData {
  const body = new FormData();
  const on = String(form.get("on") ?? "");
  if (on) body.set(field, on);
  const proof = form.get("proof");
  if (proof instanceof File && proof.size > 0) body.set("proof", proof, proof.name);
  return body;
}

async function upload(path: string, body: FormData): Promise<MaterialPage> {
  const out = await api.upload<MaterialPage>(path, body);
  refresh();
  return out;
}

export async function productionReceived(id: string, productionId: string, form: FormData): Promise<Result<MaterialPage>> {
  return attempt(() => upload(`${base(id)}/productions/${enc(productionId)}/received`, withProof("receivedOn", form)));
}

export async function cancelProduction(id: string, productionId: string): Promise<Result<MaterialPage>> {
  return attempt(() => step(`${base(id)}/productions/${enc(productionId)}/cancel`));
}

export async function crmTeams(): Promise<Result<CrmTeam[]>> {
  return attempt(async () => (await api.get<{ teams: CrmTeam[] }>("/admin/materials/teams")).teams);
}

export type DistributionInput = { teamId: string; recipientId: string | null; quantity: number; purpose: string | null };

export async function askToDistribute(id: string, input: DistributionInput): Promise<Result<MaterialPage>> {
  return attempt(() => step(`${base(id)}/distributions`, input));
}

export async function recordDistributed(id: string, distributionId: string, form: FormData): Promise<Result<MaterialPage>> {
  return attempt(() => upload(`${base(id)}/distributions/${enc(distributionId)}/distributed`, withProof("distributedOn", form)));
}

export async function cancelDistribution(id: string, distributionId: string): Promise<Result<MaterialPage>> {
  return attempt(() => step(`${base(id)}/distributions/${enc(distributionId)}/cancel`));
}
