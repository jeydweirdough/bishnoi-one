import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { ActivityItem, ActivitySummary, Paged } from "@/src/platform/lib/types";
import { ActivityList } from "../components/crm/activity-list";

export const metadata = { title: "Home" };

/** What's on your plate: what's late, what's due today, and what you did lately. */
export default async function HomePage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const first = me.user.fullName.split(" ")[0];
  const seesActivities = can(me, "activities.view");
  const [counts, todo, recent] = seesActivities
    ? await Promise.all([
        load<ActivitySummary>("/activities/summary?owner=me"),
        load<Paged<ActivityItem>>("/activities?owner=me&state=open&limit=15"),
        load<Paged<ActivityItem>>("/activities?owner=me&state=done&limit=8"),
      ])
    : [null, null, null];

  const tiles = counts && [
    { key: "overdue", label: "Overdue", n: counts.overdue, tone: counts.overdue ? "text-danger" : "text-ink" },
    { key: "today", label: "Due today", n: counts.today, tone: "text-ink" },
    { key: "upcoming", label: "Coming up", n: counts.upcoming, tone: "text-ink" },
  ];

  return (
    <>
      <PageHeader
        title={`${fmt.greeting()}, ${first}`}
        actions={
          <>
            {can(me, "customers.create") && (
              <>
                <LinkButton href="/companies/new" size="sm" icon={<Plus className="size-3.5" aria-hidden />}>
                  Company
                </LinkButton>
                <LinkButton href="/contacts/new" size="sm" icon={<Plus className="size-3.5" aria-hidden />}>
                  Contact
                </LinkButton>
              </>
            )}
            {seesActivities && (
              <LinkButton href="/activities" size="sm" variant="primary">
                Activities
              </LinkButton>
            )}
          </>
        }
      >
        {me.role?.name}
        {me.team ? ` in ${me.team.name}` : ""}
      </PageHeader>

      {!seesActivities ? (
        <Sheet className="px-5 py-8 text-center text-ink-2">Your role doesn&apos;t include activities, so there&apos;s nothing to list here.</Sheet>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-3">
            {tiles!.map((t) => (
              <Link key={t.key} href={`/activities?state=${t.key}&owner=me`} className="rounded-[3px] bg-sheet px-5 py-4 shadow-sheet hover:shadow-overlay">
                <p className="text-meta text-ink-3">{t.label}</p>
                <p className={`text-title tabular-nums ${t.tone}`}>{t.n}</p>
              </Link>
            ))}
          </div>

          <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
            <Sheet className="px-5 pt-4 pb-2">
              <SectionTitle
                icon="followUps"
                action={
                  todo!.total > todo!.items.length && (
                    <Link href="/activities?owner=me" className="text-meta text-hema hover:underline">
                      All {todo!.total}
                    </Link>
                  )
                }
              >
                Your to-do
              </SectionTitle>
              <ActivityList activities={todo!.items} org={me.org} hide={["owner"]} empty="Nothing planned. Meetings and tasks you plan land here." />
            </Sheet>
            <Sheet className="px-5 pt-4 pb-2">
              <SectionTitle icon="history">What you did lately</SectionTitle>
              <ActivityList activities={recent!.items} org={me.org} hide={["owner"]} empty="Nothing logged yet." />
            </Sheet>
          </div>
        </div>
      )}
    </>
  );
}
