import "server-only";
import type { Account } from "@/src/platform/lib/account";
import { moduleByAppKey, moduleByKey, type ModuleDef } from "@/src/platform/lib/modules";
import type { MyModule } from "./module-switcher";

/**
 * The modules this person has: the applications Bishnoi One Platform gives them
 * (and their company has), each matched to its module here, with its current
 * app's address while it's still moving in.
 */
export function myModules(me: Account): MyModule[] {
  // In the order they were given: the first is where they start (primaryModule).
  const byGrant = [...me.apps].sort((a, b) => (a.grantedAt ?? "").localeCompare(b.grantedAt ?? ""));
  const given: MyModule[] = byGrant.flatMap((a) => {
    const m = moduleByAppKey(a.key);
    return m && !m.accountOnly ? [{ key: m.key, oldUrl: a.appUrl }] : [];
  });
  // The Admin Console: the company's administrators, and Bishnoi One's staff, whatever they were given.
  return me.isCompanyAdmin || me.staff ? [...given, { key: "platform", oldUrl: null }] : given;
}

/**
 * Where someone starts (decided 2026-10-24): a company's administrators and
 * Bishnoi One's staff in the Admin Console, their main place; everyone else
 * straight into the first module they were given that's built, rather than a
 * page of tiles; null with nothing at all. The module switcher takes either to the rest.
 */
export function primaryModule(me: Account): ModuleDef | null {
  if (me.isCompanyAdmin || me.staff) return moduleByKey("platform");
  const mine = myModules(me)
    .map((x) => moduleByKey(x.key))
    .filter((m): m is ModuleDef => m !== null);
  return mine.find((m) => m.status === "live") ?? mine[0] ?? null;
}
