import { Nav } from "../shell/nav";
import { ViewingBanner } from "../shell/viewing-banner";
import { redirect } from "next/navigation";
import { getMe } from "../lib/api";
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

export async function ShellLayout({ children }: { children: React.ReactNode }) {
  const me = await getMe();
  // Every page, not only the sign-in. One session opens every Orbit app —
  // the cookie is shared — so somebody signed in to an app that is theirs
  // arrives here already authenticated, and nothing else would ask whether
  // this one is. Asked once, above every screen, before any of them load.
  if (THIS_APP && !canUseThisApp(me)) redirect("/login?denied=1");
  // The shell serves the companies list itself, and the Platform app is that
  // list, so neither of them is stranded by having no company open.
  const stranded = me.org === null && Boolean(THIS_APP) && THIS_APP !== "platform";
  return (
    <>
      {/* Above everything, on every page: these are somebody else's screens. */}
      {me.viewedBy && <ViewingBanner who={me.user.fullName} company={me.org?.name ?? "their company"} />}
      <div className="min-h-dvh lg:grid lg:grid-cols-[16.5rem_minmax(0,1fr)]">
        <Nav me={me} />
        <main className="min-w-0 px-4 pt-4 pb-12 sm:px-6 lg:px-8 lg:pt-8">
          <div className="mx-auto max-w-[70rem]">{stranded ? <NoCompany /> : children}</div>
        </main>
      </div>
    </>
  );
}
