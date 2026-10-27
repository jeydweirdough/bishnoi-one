import { cookies } from "next/headers";
import { Suspense } from "react";
import { Notices } from "@/src/platform/app/notices";
import { getMe } from "@/src/platform/lib/api";
import { NavProgress } from "@/src/platform/shell/nav-progress";
import { LinkButton } from "@/src/platform/ui/ant-button";
import { Sheet } from "@/src/platform/ui/sheet";
import { Nav, type Unset, type Waiting } from "./nav";
import { OneActions } from "@/src/one/one-actions";
import { getAccount } from "@/src/platform/lib/account";
import { myModules } from "@/src/one/mine";
import { TopActions, type Notification } from "./top-actions";

// The CRM's frame inside the one app (decided 2026-10-23): its sidebar, its own
// actions at the top (search, bell, your CRM pages), then the page. The one
// app's bar above it says who you are and switches modules. The Platform
// decides who may open the CRM (its pass), so nothing here asks again.

/** Signed in to the CRM with no company open (a Platform staff session): every CRM screen belongs to one. */
function NoCompany() {
  return (
    <Sheet className="px-6 py-10 text-center">
      <h1 className="text-heading">Open a company first</h1>
      <p className="mx-auto mt-1 max-w-md text-ink-2">Every CRM screen belongs to a company. Open one from Bishnoi One, then come back.</p>
      <LinkButton href="/" className="mt-5">
        All modules
      </LinkButton>
    </Sheet>
  );
}

/** `waiting`: how many things wait on this person, by kind, for the sidebar's counts.
 *  `unset`: how many things aren't set up yet, for its red counts.
 *  `notifications`: the CRM's own, for the bell, and `allHref` where they're all listed. */
export async function ShellLayout({ children, waiting, unset, notifications, allHref, search }: { children: React.ReactNode; waiting?: Waiting; unset?: Unset; notifications?: Promise<Notification[]>; allHref?: string; search?: React.ReactNode }) {
  const me = await getMe();
  // The modules this person was given, for the switcher at the top of the sidebar.
  const mine = myModules(await getAccount());
  const stranded = me.org === null;
  // The sidebar as it was left: full, or collapsed to its icons.
  const rail = (await cookies()).get("bishnoi_nav")?.value === "rail";
  const actions = (
    <TopActions allHref={allHref} search={stranded ? undefined : search}>
      <OneActions links={[{ href: "/crm/account", label: "Your profile" }, { href: "/crm/account/mailbox", label: "Your mailbox" }]} />
    </TopActions>
  );
  return (
    <>
      {/* Says at once that a link was clicked; the sidebar stays, the page loads beside it. */}
      <Suspense fallback={null}>
        <NavProgress />
      </Suspense>
      <div className="group/shell lg:grid lg:grid-cols-[auto_minmax(0,1fr)]">
        <Nav me={me} mine={mine} waiting={waiting} unset={unset} rail={rail} actions={actions} />
        <main className="min-w-0 px-4 pt-4 pb-12 sm:px-6 lg:px-8 lg:pt-4">
          <header className="mb-4 hidden justify-end lg:flex">{actions}</header>
          <div className="mx-auto max-w-[70rem] lg:group-has-[aside[data-rail=true]]/shell:max-w-[88rem]">
            {/* Announcements from Bishnoi One Platform (kept in Discord), for the CRM and for everyone. */}
            <Notices timeZone={me.org?.timezone} />
            {stranded ? <NoCompany /> : children}
          </div>
        </main>
      </div>
    </>
  );
}
