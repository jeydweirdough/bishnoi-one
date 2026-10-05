import Link from "next/link";
import { Bars } from "@/src/platform/ui/bars";
import { Figure } from "@/src/platform/ui/figure";
import { Flag } from "@/src/platform/ui/marks";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { Dashboard } from "@/src/platform/lib/types";

// Admin's own front page: who can sign in, and what about this company is
// half-set. Every other app opens on its own work, and this is Admin's —
// running the company, rather than the first settings screen in the list.

export const metadata = { title: "Admin" };

export default async function Page() {
  const me = await getCompanyMe();
  const { admin } = await load<Dashboard>("/me/dashboard");
  // Those with access, less the ones switched off: the bar for people
  // actually able to work today.
  const working = admin === null ? 0 : Math.max(0, admin.people - admin.switchedOff);

  return (
    <>
      <PageHeader title={me.org.name}>
        Who can sign in, and anything about this company that is set up only halfway.
      </PageHeader>

      {admin === null ? (
        <Sheet className="px-5 py-4">
          <Empty icon="account" title="Nothing to see here yet">
            This company&apos;s figures aren&apos;t ready for you. Everything you run is in the sidebar.
          </Empty>
        </Sheet>
      ) : (
        <>
          <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
            <Sheet className="grid divide-y divide-rule sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              <Figure label="People with access" value={admin.people} href="/settings/people" />
              <Figure label="Switched off" value={admin.switchedOff} href="/settings/people" />
              <Figure label="With no role yet" value={admin.noRoleCount} flag href="/settings/people" />
            </Sheet>
            <Sheet className="px-5 pt-4 pb-4">
              <SectionTitle icon="people">Who can sign in</SectionTitle>
              {/* Signed in, switched off and no-role-yet overlap, so they are
                  three bars and never one divided circle: a pie would claim they
                  add up to the company, and they do not. */}
              <Bars
                rows={[
                  { label: "Working today", value: working, href: "/settings/people" },
                  { label: "Switched off", value: admin.switchedOff, href: "/settings/people" },
                  { label: "No role yet", value: admin.noRoleCount, href: "/settings/people", flag: true },
                ]}
                unit="people"
              />
            </Sheet>
          </div>

          {(admin.noRole.length > 0 || admin.noPrices.length > 0) && (
            <Sheet className="mb-5 px-5 pt-4 pb-4">
              <SectionTitle icon="person">Worth a look</SectionTitle>
              <ul className="mt-2 space-y-1.5 text-sm">
                {admin.noRole.map((p) => (
                  <li key={p.id}>
                    <Link href={`/settings/people/${p.id}`} className="font-medium text-hema hover:underline">
                      {p.name}
                    </Link>
                    <span className="text-ink-3"> can sign in but has no role, so sees nothing.</span>
                  </li>
                ))}
                {admin.noPrices.length > 0 && (
                  <li>
                    <Flag letter="!">{admin.noPrices.join(", ")} can&apos;t quote yet</Flag>
                    <span className="text-ink-3"> · no prices switched on. </span>
                    <Link href="/settings/pricing" className="font-medium text-hema hover:underline">
                      Set which prices they may use
                    </Link>
                    <span className="text-ink-3">.</span>
                  </li>
                )}
              </ul>
            </Sheet>
          )}
        </>
      )}

      <Sheet className="px-5 py-4">
        <SectionTitle icon="settings">What Admin decides</SectionTitle>
        <dl className="mt-2 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="font-semibold">Access</dt>
            <dd className="text-ink-2">Who can sign in, the roles they hold, and the teams they sell or work in.</dd>
          </div>
          <div>
            <dt className="font-semibold">Business rules</dt>
            <dd className="text-ink-2">Prices, lists, money and date formats, order rules, retention and goals.</dd>
          </div>
          <div>
            <dt className="font-semibold">The company itself</dt>
            <dd className="text-ink-2">Its name and the other Bishnoi One apps it reaches, with the log of what changed.</dd>
          </div>
        </dl>
      </Sheet>
    </>
  );
}
