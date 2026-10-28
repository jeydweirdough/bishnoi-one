"use server";

// Operators (app/routers/operators.py, feature plan step 5): a switch on a Bishnoi One account.

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/console/platform/lib/api";
import { attempt, type Result } from "@/src/modules/console/platform/lib/result";

export type Operator = { id: string; no: number | null; email: string; fullName: string; isOperator: boolean; status: string; lastSignInAt: string | null; createdAt: string };

export async function findAccounts(q: string): Promise<Result<Operator[]>> {
  return attempt(async () => (await api.get<{ found: Operator[] }>(`/platform/operators?q=${enc(q)}`)).found);
}

export async function setOperator(id: string, isOperator: boolean): Promise<Result<Operator>> {
  return attempt(async () => {
    const r = await api.put<{ operator: Operator }>(`/platform/operators/${enc(id)}`, { isOperator });
    refresh();
    return r.operator;
  });
}
