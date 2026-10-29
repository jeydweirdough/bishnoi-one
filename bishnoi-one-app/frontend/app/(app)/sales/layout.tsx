// The Sales app's frame (feature plan step 11): the shared sidebar, then the page. It runs on the Operations
// service (Inventory's API), with its own session.
import { cookies } from "next/headers";
import type { ReactNode } from "react";
import { OneActions } from "@/src/one/one-actions";
import { myModules } from "@/src/one/mine";
import { getAccount } from "@/src/platform/lib/account";
import { ModuleActions } from "@/src/platform/shell/module-actions";
import { getMe, load } from "@/src/modules/inventory/platform/lib/api";
import { SalesNav } from "@/src/modules/sales/nav";
import type { SalesOrderBrief } from "@/src/modules/sales/types";

export default async function Layout({ children }: { children: ReactNode }) {
  const [me, account] = await Promise.all([getMe(), getAccount()]);
  const waiting = me.permissions?.includes("sales.approve")
    ? await load<SalesOrderBrief[]>("/inventory/sales-orders?status=pending").then((x) => x.length).catch(() => 0)
    : 0;
  const rail = (await cookies()).get("bishnoi_nav")?.value === "rail";
  const actions = (
    <ModuleActions>
      <OneActions />
    </ModuleActions>
  );
  return (
    <div className="group/shell lg:grid lg:grid-cols-[auto_minmax(0,1fr)]">
      <SalesNav me={me} mine={myModules(account)} waiting={waiting} rail={rail} actions={actions} />
      <main className="min-w-0 px-4 pt-4 pb-12 sm:px-6 lg:px-8 lg:pt-4">
        <header className="mb-4 hidden justify-end lg:flex">{actions}</header>
        <div className="mx-auto max-w-[70rem]">{children}</div>
      </main>
    </div>
  );
}
