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
    return m && !m.accountOnly && !m.staffSignIn ? [{ key: m.key, oldUrl: a.appUrl }] : [];
  });
  // People and access: the company's administrators, whatever they were given.
  return me.isCompanyAdmin ? [...given, { key: "platform", oldUrl: null }] : given;
}

/**
 * Where someone starts (decided 2026-10-24): straight into the first module they
 * were given that's built, rather than a page of tiles; People and access for an
 * administrator with nothing else; null with nothing at all.
 */
export function primaryModule(me: Account): ModuleDef | null {
  const mine = myModules(me)
    .map((x) => moduleByKey(x.key))
    .filter((m): m is ModuleDef => m !== null);
  return mine.find((m) => m.status === "live") ?? mine[0] ?? null;
}
