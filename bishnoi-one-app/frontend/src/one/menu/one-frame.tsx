import { cookies } from "next/headers";
import { Suspense, type ReactNode } from "react";
import { getAccount } from "@/src/platform/lib/account";
import { CrumbsSlot } from "@/src/platform/shell/crumbs";
import { NavProgress } from "@/src/platform/shell/nav-progress";
import { OneActions } from "@/src/one/one-actions";
import { OneSidebar } from "./one-sidebar";

/** The frame of the one app's own pages (Home, Reports): the one sidebar, your account at the top right, the page. */
export async function OneFrame({ children }: { children: ReactNode }) {
  const [me, jar] = await Promise.all([getAccount(), cookies()]);
  const rail = jar.get("bishnoi_nav")?.value === "rail";
  const actions = <OneActions />;
  return (
    <>
      <Suspense fallback={null}>
        <NavProgress />
      </Suspense>
      <div className="group/shell lg:grid lg:grid-cols-[auto_minmax(0,1fr)]">
        <OneSidebar company={me.company?.name} rail={rail} actions={actions} />
        <main className="min-w-0 px-4 pt-4 pb-12 sm:px-6 lg:px-8 lg:pt-4">
          <header className="mx-auto mb-4 hidden max-w-[70rem] items-center gap-3 lg:flex lg:group-has-[aside[data-rail=true]]/shell:max-w-[88rem]">
            <CrumbsSlot />
            {actions}
          </header>
          <div className="mx-auto max-w-[70rem] lg:group-has-[aside[data-rail=true]]/shell:max-w-[88rem]">{children}</div>
        </main>
      </div>
    </>
  );
}
