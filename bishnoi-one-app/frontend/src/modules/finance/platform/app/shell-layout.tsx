import { cookies } from "next/headers";
import { Suspense, type ReactNode } from "react";
import { Notices } from "@/src/platform/app/notices";
import { ModuleActions } from "@/src/platform/shell/module-actions";
import { NavProgress } from "@/src/platform/shell/nav-progress";
import { getMe } from "../lib/api";
import { Nav } from "../shell/nav";

// Finance's frame inside the one app (decided 2026-10-23): its sidebar, its own
// actions at the top (its bell, your profile here), then the page. The one app's
// bar above it says who you are and switches modules; the Platform decides who
// may open Finance (its pass), so nothing here asks again. Written by
// scripts/move-module.mjs.
type Props = { children: ReactNode; waiting?: Record<string, number>; unset?: Record<string, number>; bell?: ReactNode };

export async function ShellLayout({ children, waiting, unset, bell }: Props) {
  const me = await getMe();
  const rail = (await cookies()).get("bishnoi_nav")?.value === "rail";
  const actions = <ModuleActions bell={bell} profileHref="/finance/account" />;
  return (
    <>
      <Suspense fallback={null}>
        <NavProgress />
      </Suspense>
      <div className="group/shell lg:grid lg:grid-cols-[auto_minmax(0,1fr)]">
        <Nav me={me} waiting={waiting} unset={unset} rail={rail} actions={actions} />
        <main className="min-w-0 px-4 pt-4 pb-12 sm:px-6 lg:px-8 lg:pt-4">
          <header className="mb-4 hidden justify-end lg:flex">{actions}</header>
          <div className="mx-auto max-w-[70rem] lg:group-has-[aside[data-rail=true]]/shell:max-w-[88rem]">
            <Notices timeZone={me.org?.timezone} />
            {children}
          </div>
        </main>
      </div>
    </>
  );
}
