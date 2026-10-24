import "server-only";
import { notFound } from "next/navigation";
import { getMe } from "@/src/modules/inventory/platform/lib/api";
import type { Action, ModuleAccess, TeamAccess } from "@/src/modules/inventory/platform/lib/types";

/** The sales module a page belongs to. The module layout already turned away anyone without access. */
export async function crmModule(key: string): Promise<ModuleAccess> {
  const me = await getMe();
  const mod = me.modules.find((m) => m.key === key && m.kind === "crm");
  if (!mod) notFound();
  return mod;
}

/** A department module's page: 404 anywhere but its own module (/m/b2c/products isn't a thing). */
export async function departmentModule(key: string, expected: "finance" | "inventory"): Promise<ModuleAccess> {
  const me = await getMe();
  const mod = me.modules.find((m) => m.key === key && m.key === expected);
  if (!mod) notFound();
  return mod;
}

/** Whether the person may do this anywhere in the module. The API checks again on every call. */
export function may(mod: ModuleAccess, action: Action): boolean {
  return mod.actions.includes(action);
}

export function teamsWhere(mod: ModuleAccess, action: Exclude<Action, "view">): TeamAccess[] {
  return mod.teams.filter((t) => t.actions.includes(action));
}

/** Every sales division this person sells in, as one workspace.
 *
 *  Customers, Follow-ups and Retention are the same pages whichever division a
 *  record is in, so they are one set of pages over one merged list. The
 *  division is something a record carries, not a place you navigate to. */
export type CrmWorkspace = {
  divisions: ModuleAccess[];
  /** True when there is more than one, and so something to tell apart. */
  manyDivisions: boolean;
  /** Every team they are on, each saying which division it belongs to. */
  teams: (TeamAccess & { division: string; divisionName: string })[];
};

export async function crmWorkspace(): Promise<CrmWorkspace> {
  const me = await getMe();
  const divisions = me.modules.filter((m) => m.kind === "crm");
  if (divisions.length === 0) notFound();
  return {
    divisions,
    manyDivisions: divisions.length > 1,
    teams: divisions.flatMap((d) => d.teams.map((t) => ({ ...t, division: d.key, divisionName: d.name }))),
  };
}

/** Whether they may do this in at least one of their divisions. The API checks
 *  again per record, against that record's own division and team. */
export function mayAnywhere(ws: CrmWorkspace, action: Action): boolean {
  return ws.divisions.some((d) => d.actions.includes(action));
}

/** The teams they may do this in, across every division. */
export function teamsFor(ws: CrmWorkspace, action: Exclude<Action, "view">) {
  return ws.teams.filter((t) => t.actions.includes(action));
}
