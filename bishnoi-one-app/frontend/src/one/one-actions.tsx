import { getAccount } from "@/src/platform/lib/account";
import { AccountMenu, type AccountLink } from "./account-menu";
import { myModules } from "./mine";
import { ModuleSwitcher } from "./module-switcher";

/**
 * The top right of every page, as before the one app (decided 2026-10-24, in
 * place of a bar across the top): your modules (the old app launcher), then
 * you: your company, your own pages in this module (`links`), switching
 * company, signing out. A module puts its own actions (search, its bell) before these.
 */
export async function OneActions({ links = [] }: { links?: AccountLink[] }) {
  const me = await getAccount();
  return (
    <>
      <ModuleSwitcher mine={myModules(me)} compact />
      <AccountMenu compact id={me.id} name={me.fullName} email={me.email} companies={me.companies} links={links} />
    </>
  );
}
