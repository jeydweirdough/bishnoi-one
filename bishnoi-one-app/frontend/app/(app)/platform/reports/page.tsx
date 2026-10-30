import Link from "next/link";
import { accountSend } from "@/src/platform/lib/account";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export const metadata = { title: "Reports Center" };

type Info = { key: string; name: string; about: string; dated: boolean };

// The Admin Console's Reports Center (2026-10-30): people reports only, from the Platform: who's here,
// who signs in, who can open what, roles and security events. No money: each app's own reports (Finance,
// CRM, Inventory) are opened in that app; old links to them here go there (src/platform/proxy.ts).
export default async function ReportsCenter() {
  const list = await accountSend<{ reports: Info[] }>("GET", "/identity/company/reports").catch(() => null);
  return (
    <>
      <PageHeader title="Reports Center">Your company&apos;s people in reports: open one, filter, sort and export it. Each app&apos;s own reports are in that app.</PageHeader>
      {!list ? (
        <Sheet>
          <Empty icon="reports" title="Reports can't be loaded right now">
            Refresh to try again.
          </Empty>
        </Sheet>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {list.reports.map((r) => (
            <Link key={r.key} href={`/platform/reports/people/${r.key}`} className="group rounded-xl border border-rule bg-sheet px-5 py-4 transition-colors hover:border-rule-strong hover:bg-bench">
              <span className="flex items-center gap-2 text-sm font-semibold text-ink">
                <Icon name={r.key === "security-events" ? "password" : r.key === "roles" ? "roles" : r.key === "access-by-app" ? "apps" : "people"} className="size-4 text-ink-3" />
                {r.name}
              </span>
              <span className="mt-1 block text-meta text-ink-3">{r.about}</span>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
