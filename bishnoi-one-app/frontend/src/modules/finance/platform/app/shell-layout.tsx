import { myModules } from "@/src/one/mine";
import { cookies } from "next/headers";
import { Suspense, type ReactNode } from "react";
import { Notices } from "@/src/platform/app/notices";
import { OneActions } from "@/src/one/one-actions";
import { ModuleActions } from "@/src/platform/shell/module-actions";
import { NavProgress } from "@/src/platform/shell/nav-progress";
import { getMe } from "../lib/api";
import { Nav } from "../shell/nav";
import { FinancePrintFrame } from "@/src/modules/finance/printing/frame";
import { getAccount } from "@/src/platform/lib/account";

// Finance's frame inside the one app (decided 2026-10-23): its sidebar, its own
// actions at the top (its bell, your profile here), then the page. The one app's
// bar above it says who you are and switches modules; the Platform decides who
// may open Finance (its pass), so nothing here asks again. Written by
// scripts/move-module.mjs.
// `footer`: what Finance shows at the bottom of its sidebar (its version, src/modules/finance/version).
type Props = { children: ReactNode; waiting?: Record<string, number>; unset?: Record<string, number>; bell?: ReactNode; footer?: ReactNode };

export async function ShellLayout({ children, waiting, unset, bell, footer }: Props) {
  const me = await getMe();
  // Reuse the cached Platform identity already read by OneActions, not Finance's
  // generic development org label, to choose company-specific print branding.
  const account = await getAccount();
  const mine = myModules(account);
  const rail = (await cookies()).get("bishnoi_nav")?.value === "rail";
  // Its bell, then your modules and you (src/one/one-actions.tsx): the top right, as before the one app.
  const actions = (
    <ModuleActions bell={bell}>
      <OneActions links={[{ href: "/finance/account", label: "Your profile" }]} />
    </ModuleActions>
  );
  return (
    <>
      <Suspense fallback={null}>
        <NavProgress />
      </Suspense>
      <div className="finance-shell group/shell lg:grid lg:grid-cols-[auto_minmax(0,1fr)]">
        <Nav me={me} mine={mine} waiting={waiting} unset={unset} rail={rail} actions={actions} footer={footer} />
        <main className="finance-shell-main min-w-0 px-4 pt-4 pb-12 sm:px-6 lg:px-8 lg:pt-4">
          <header className="finance-shell-actions mb-4 hidden justify-end lg:flex">{actions}</header>
          <div className="finance-shell-width mx-auto max-w-[70rem] lg:group-has-[aside[data-rail=true]]/shell:max-w-[88rem]">
            <div className="finance-shell-notices"><Notices timeZone={me.org?.timezone} /></div>
            <FinancePrintFrame org={me.org} company={account.company}>{children}</FinancePrintFrame>
          </div>
        </main>
      </div>
    </>
  );
}
