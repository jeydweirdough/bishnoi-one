import { Nav, type Unset, type Waiting } from "../shell/nav";
import { TopActions, type Notification } from "../shell/topbar";
import { Suspense } from "react";
import { NavProgress } from "../shell/nav-progress";
import { Notices } from "./notices";
import { ViewingBanner } from "../shell/viewing-banner";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { getMe } from "../lib/api";
import { loadAddresses } from "../lib/addresses";
import { THIS_APP, canUseThisApp, platformHome, thisAppLabel } from "../lib/apps";
import { LinkButton } from "../ui/button";
import { Sheet } from "../ui/sheet";

/**
 * Signed in to the platform, which is in no company, inside an app whose every
 * screen belongs to one.
 *
 * A Developer Admin lands here by opening a kept address — the sidebar only
 * offers the companies list while no company is open. The API calls this "a
 * plain answer, not a fault", so this says the same rather than letting each
 * screen throw on the first thing it asks for.
 */
function NoCompany() {
  return (
    <Sheet className="px-6 py-10 text-center">
      <h1 className="text-heading">Open a company first</h1>
      <p className="mx-auto mt-1 max-w-md text-ink-2">
        You&apos;re signed in to the platform, which is in no company{thisAppLabel() ? `, and every ${thisAppLabel()} screen belongs to one` : ""}.
      </p>
      <LinkButton href={platformHome()} className="mt-5">
        Choose a company
      </LinkButton>
    </Sheet>
  );
}

/** `waiting`: how many things wait on this person, by kind, for the sidebar's counts.
 *  `unset`: how many things aren't set up yet, for its red counts.
 *  `notifications`: the app's own, for the bell (left out: no bell), and `allHref` where they're all listed. */
export async function ShellLayout({ children, waiting, unset, notifications, allHref, search }: { children: React.ReactNode; waiting?: Waiting; unset?: Unset; notifications?: Promise<Notification[]>; allHref?: string; search?: React.ReactNode }) {
  await loadAddresses();
  const me = await getMe();
  // Every page, not only the sign-in. One session opens every Bishnoi One app —
  // the cookie is shared — so somebody signed in to an app that is theirs
  // arrives here already authenticated, and nothing else would ask whether
  // this one is. Asked once, above every screen, before any of them load.
  if (THIS_APP && !canUseThisApp(me)) redirect("/login?denied=1");
  // The shell serves the companies list itself, and the Platform app is that
  // list, so neither of them is stranded by having no company open.
  const stranded = me.org === null && Boolean(THIS_APP) && THIS_APP !== "platform";
  // The sidebar as it was left: full, or collapsed to its icons.
  const rail = (await cookies()).get("bishnoi_nav")?.value === "rail";
  // The bell, then who you are: the top right of every page.
  const actions = <TopActions me={me} notifications={stranded ? undefined : notifications} allHref={allHref} search={stranded ? undefined : search} />;
  return (
    <>
      {/* Above everything, on every page: these are somebody else's screens. */}
      {me.viewedBy && <ViewingBanner who={me.user.fullName} company={me.org?.name ?? "their company"} />}
      {/* Says at once that a link was clicked; the sidebar stays, the page loads beside it. */}
      <Suspense fallback={null}>
        <NavProgress />
      </Suspense>
      <div className="group/shell min-h-dvh lg:grid lg:grid-cols-[auto_minmax(0,1fr)]">
        <Nav me={me} waiting={waiting} unset={unset} rail={rail} actions={actions} />
        <main className="min-w-0 px-4 pt-4 pb-12 sm:px-6 lg:px-8 lg:pt-4">
          {/* Wider screens: the bell and the profile at the top right (on a phone they're in the top bar). */}
          <header className="mb-4 hidden justify-end lg:flex">{actions}</header>
          <div className="mx-auto max-w-[70rem] lg:group-has-[aside[data-rail=true]]/shell:max-w-[88rem]">
            {/* Announcements from Bishnoi One Platform (kept in Discord), for this app and for everyone. */}
            <Notices timeZone={me.org?.timezone} />
            {stranded ? <NoCompany /> : children}
          </div>
        </main>
      </div>
    </>
  );
}
