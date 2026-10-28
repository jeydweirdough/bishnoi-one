"use server";

import { revalidatePath } from "next/cache";
import { accountSend } from "@/src/platform/lib/account";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { OrgBranch, OrgUnit, UnitKind } from "./types";

// A company administrator's changes to the org chart, on Bishnoi One Platform
// (/identity/organisation). The Platform sends each app the change.

const enc = encodeURIComponent;
const refresh = () => revalidatePath("/platform/organisation");

export type UnitInput = { kind: UnitKind; name: string; parentId: string | null; managerId: string | null; areas: string[] };

export async function addUnit(input: UnitInput): Promise<Result<{ unit: OrgUnit }>> {
  return attempt(async () => {
    const made = await accountSend<{ unit: OrgUnit }>("POST", "/identity/organisation/units", input);
    refresh();
    return made;
  });
}

export async function changeUnit(id: string, change: Partial<UnitInput> & { isActive?: boolean }): Promise<Result> {
  return attempt(async () => {
    await accountSend("PATCH", `/identity/organisation/units/${enc(id)}`, change);
    refresh();
    return null;
  });
}

export type BranchInput = { name: string; address: string | null };

export async function addBranch(input: BranchInput): Promise<Result<{ branch: OrgBranch }>> {
  return attempt(async () => {
    const made = await accountSend<{ branch: OrgBranch }>("POST", "/identity/organisation/branches", input);
    refresh();
    return made;
  });
}

export async function changeBranch(id: string, change: Partial<BranchInput> & { isActive?: boolean }): Promise<Result> {
  return attempt(async () => {
    await accountSend("PATCH", `/identity/organisation/branches/${enc(id)}`, change);
    refresh();
    return null;
  });
}

export type PlacementInput = { mainUnitId: string | null; otherUnitIds: string[]; branchId: string | null };

export async function placePerson(id: string, input: PlacementInput): Promise<Result> {
  return attempt(async () => {
    await accountSend("PUT", `/identity/organisation/people/${enc(id)}`, input);
    refresh();
    return null;
  });
}
