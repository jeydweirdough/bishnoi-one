import { AppShell } from "@/src/platform/shell/app-shell";
import { cookies } from "next/headers";
import { Suspense, type ReactNode } from "react";
import { getAccount } from "@/src/platform/lib/account";
import { OneActions } from "@/src/one/one-actions";
import { OneSidebar } from "./one-sidebar";

/** The frame of the one app's own pages (Home, Reports): the one sidebar, your account at the top right, the page. */
export async function OneFrame({ children }: { children: ReactNode }) {
  const [me, jar] = await Promise.all([getAccount(), cookies()]);
  const rail = jar.get("bishnoi_nav")?.value === "rail";
  const actions = <OneActions />;
  return (
    <>
      <AppShell nav={<OneSidebar company={me.company?.name} rail={rail} actions={actions} />} actions={actions}>{children}</AppShell>
    </>
  );
}
