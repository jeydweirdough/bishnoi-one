import { AppShell } from "@/src/platform/shell/app-shell";
import { cookies } from "next/headers";
import { Suspense, type ReactNode } from "react";
import { Notices } from "@/src/platform/app/notices";
import { OneActions } from "@/src/one/one-actions";
import { getAccount } from "@/src/platform/lib/account";
import { myModules } from "@/src/one/mine";
import { ModuleActions } from "@/src/platform/shell/module-actions";
import { getMe } from "../lib/api";
import { Nav } from "../shell/nav";

// Pharmacy's frame inside the one app (decided 2026-10-23): its sidebar, its own
// actions at the top (its bell, your profile here), then the page. The one app's
// bar above it says who you are and switches modules; the Platform decides who
// may open Pharmacy (its pass), so nothing here asks again. Written by
// scripts/move-module.mjs.
type Props = { children: ReactNode; waiting?: Record<string, number>; unset?: Record<string, number>; bell?: ReactNode };

export async function ShellLayout({ children, unset, bell }: Props) {
  const me = await getMe();
  // The modules this person was given, for the switcher at the top of the sidebar.
  const mine = myModules(await getAccount());
  const rail = (await cookies()).get("bishnoi_nav")?.value === "rail";
  // Its bell, then your modules and you (src/one/one-actions.tsx): the top right, as before the one app.
  const actions = (
    <ModuleActions bell={bell}>
      <OneActions links={[{ href: "/pharmacy/account", label: "Your profile" }]} />
    </ModuleActions>
  );
  return (
    <>
      <AppShell nav={<Nav me={me} mine={mine} unset={unset} rail={rail} actions={actions} />} actions={actions}>
            <Notices timeZone={me.org?.timezone} />
            {children}
          </AppShell>
    </>
  );
}
