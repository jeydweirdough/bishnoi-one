"use server";

// Operators (app/routers/operators.py, feature plan step 5): a switch on a Bishnoi One account.

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/console/platform/lib/api";
import { attempt, type Result } from "@/src/modules/console/platform/lib/result";

export type Operator = { id: string; no: number | null; email: string; fullName: string; isOperator: boolean; status: string; lastSignInAt: string | null; createdAt: string };

/** A new operator with an email of their own: one email, one account (decided 2026-10-29). */
export async function addOperator(input: { email: string; fullName: string; password: string }): Promise<Result<Operator>> {
  return attempt(async () => {
    const r = await api.post<{ operator: Operator }>("/platform/operators", input);
    refresh();
    return r.operator;
  });
}

/** Find a person: any account, with the company it belongs to (or that it's an operator's). */
export type FoundPerson = Operator & {
  memberships: { id: string; companyId: string; company: string; companySlug: string; status: string; isCompanyAdmin: boolean; offDomain: boolean }[];
};

export async function findPeople(q: string): Promise<Result<FoundPerson[]>> {
  return attempt(async () => (await api.get<{ people: FoundPerson[] }>(`/platform/people?q=${enc(q)}`)).people);
}

export async function setOperator(id: string, isOperator: boolean): Promise<Result<Operator>> {
  return attempt(async () => {
    const r = await api.put<{ operator: Operator }>(`/platform/operators/${enc(id)}`, { isOperator });
    refresh();
    return r.operator;
  });
}
