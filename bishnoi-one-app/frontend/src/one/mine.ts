import "server-only";
import type { Account } from "@/src/platform/lib/account";
import { MODULES, moduleByAppKey, moduleByKey, type ModuleDef } from "@/src/platform/lib/modules";
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
    if (!m || m.accountOnly) return [];
    // Sales runs in the Operations service (Inventory's): it comes with Inventory, while the catalogue has it on (step 11).
    const withSales = m.key === "inventory" && me.features?.["app:sales"] !== false ? [{ key: "sales" as const, oldUrl: null }] : [];
    return [{ key: m.key, oldUrl: a.appUrl }, ...withSales];
  });
  if (!(me.isCompanyAdmin || me.staff)) return given;
  // A company's administrators, and Bishnoi One's staff, see every module (decided 2026-10-25): what
  // the company has (Platform gives administrators all of it), the ones coming soon, and the Admin Console.
  const soon: MyModule[] = MODULES.filter((m) => m.status === "soon" && !given.some((x) => x.key === m.key)).map((m) => ({ key: m.key, oldUrl: null }));
  return [...given, ...soon, { key: "platform", oldUrl: null }];
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
