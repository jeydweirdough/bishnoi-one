import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";
import { enterSoftly } from "@/src/platform/lib/enter";
import type { ModuleKey } from "@/src/platform/lib/modules";
import { moduleCookie } from "@/src/platform/lib/session-cookie";
import { DataCleanupPage } from "@/src/platform/recycle/screen";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { logSources, PLATFORM } from "./activity";

// Data clean-up and the recycle bin, for every app, in the Admin Console (2026-10-31, decision B2): an app at a
// time (its records are its own), each app's engine (/data-cleanup) read with the company administrator's session
// there. People's recycle bin is Bishnoi One's own (People > Recycle bin), reached from the first tab.

const HERE = "/platform/company/data-cleanup";

export async function DataCleanupConsolePage({ search }: { search: Record<string, string | string[] | undefined> }) {
  if (!(await getAccount()).isCompanyAdmin) redirect("/platform");
  const apps = (await logSources()).filter((s) => s.key !== PLATFORM && s.module);
  const asked = typeof search.app === "string" ? search.app : "";
  const unavailable = new Set((typeof search.unavailable === "string" ? search.unavailable : "").split(",").filter(Boolean));
  const app = apps.find((a) => a.key === asked) ?? apps[0];
  const tabs = (
    <nav className="mb-4 flex flex-wrap gap-1" aria-label="Which app">
      <Link href="/platform/roles/people/bin" className="rounded-md px-3 py-1 text-meta text-ink-3 hover:bg-bench">
        People
      </Link>
      {apps.map((a) => (
        <Link
          key={a.key}
          href={`${HERE}?app=${a.key}`}
          aria-current={app?.key === a.key ? "page" : undefined}
          className={`rounded-md px-3 py-1 text-meta ${app?.key === a.key ? "bg-hema-tint font-semibold text-ink" : "text-ink-3 hover:bg-bench"}`}
        >
          {a.label}
        </Link>
      ))}
    </nav>
  );
  if (!app) {
    return (
      <>
        <PageHeader title="Data clean-up" />
        {tabs}
        <Sheet>
          <Empty icon="lists" title="No apps yet">Your company&apos;s apps keep their deleted records here, each in its own recycle bin.</Empty>
        </Sheet>
      </>
    );
  }
  if (unavailable.has(app.key)) {
    return (
      <>
        <PageHeader title="Data clean-up" />
        {tabs}
        <Sheet>
          <Empty icon="lists" title={`${app.label} can't be opened just now`} actions={<Link href={`${HERE}?app=${app.key}`} className="text-sm underline">Try again</Link>}>
            Its records and recycle bin are kept by {app.label} itself; they show here once it answers.
          </Empty>
        </Sheet>
      </>
    );
  }
  // The app's session first, softly: if it can't be opened, the page comes back with it marked unavailable.
  if (!(await cookies()).get(moduleCookie(app.key))?.value) redirect(enterSoftly(app.key, `${HERE}?app=${app.key}`));
  return (
    <DataCleanupPage module={app.key as ModuleKey} path={HERE} tabs={tabs} />
  );
}
