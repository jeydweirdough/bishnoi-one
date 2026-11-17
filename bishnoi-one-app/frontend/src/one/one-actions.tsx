import { cookies } from "next/headers";
import { getAccount } from "@/src/platform/lib/account";
import { currentModule, load } from "@/src/platform/lib/api";
import { viewAsCookie } from "@/src/platform/lib/session-cookie";
import { ViewAsButton, ViewingBar, type ViewAsRole } from "./view-as";
import { AccountMenu, type AccountLink } from "./account-menu";

/**
 * The top right of every page, as before the one app (decided 2026-10-24, in
 * place of a bar across the top). No app launcher since the one menu by work (M4, 2026-11-18); then
 * you: your company, your own pages in this module (`links`), switching
 * company, signing out. A module puts its own actions (search, its bell) before these.
 */
export async function OneActions({ links = [] }: { links?: AccountLink[] }) {
  const [me, mod, jar] = await Promise.all([getAccount(), currentModule(), cookies()]);
  // View as (decided 2026-10-26): in a module, for whoever its API lets list its people; while
  // viewing, the bar across the top instead (the API answers as that person then).
  const viewing = mod && !mod.accountOnly ? jar.get(viewAsCookie(mod.key))?.value?.split("|") : undefined;
  const roles =
    mod && !mod.accountOnly && !viewing ? await load<{ roles: ViewAsRole[] }>("/auth/view-as").then((r) => r.roles, () => null) : null;
  return (
    <>
      {viewing && <ViewingBar name={viewing[1] ?? "someone"} role={viewing[2] ?? ""} />}
      {roles && roles.length > 0 && <ViewAsButton roles={roles} />}
      <AccountMenu compact id={me.id} name={me.fullName} email={me.email} companies={me.companies} links={links} viewAs={Boolean(roles && roles.length > 0)} />
    </>
  );
}
