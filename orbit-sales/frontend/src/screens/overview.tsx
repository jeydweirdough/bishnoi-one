import { Plus } from "lucide-react";
import Link from "next/link";
import { FollowUpItem } from "../components/follow-up-item";
import { LinkButton } from "@/src/platform/ui/button";
import { Figure } from "@/src/platform/ui/figure";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { ActivityItem, ActivitySummary, CompanyRow, Paged } from "@/src/platform/lib/types";
import { customerOf, dayOf, followUpRow } from "../components/crm/follow-up-rows";
import { kindOf } from "../components/crm/words";

export const metadata = { title: "Overview" };

export default async function Overview() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const seesCustomers = can(me, "customers.view");
  const seesActivities = can(me, "activities.view");
  const none: Paged<never> = { items: [], total: 0 };
  // Everything they reach, counted once; the follow-up figures are their own.
  const [companies, prospects, counts, mine, recent] = await Promise.all([
    seesCustomers ? load<Paged<CompanyRow>>("/companies?limit=1") : none,
    seesCustomers ? load<Paged<CompanyRow>>("/companies?status=prospect&limit=1") : none,
    seesActivities ? load<ActivitySummary>("/activities/summary?owner=me&kind=task") : { overdue: 0, today: 0, upcoming: 0, open: 0 },
    seesActivities ? load<Paged<ActivityItem>>("/activities?owner=me&kind=task&state=open&limit=100") : none,
    seesActivities ? load<Paged<ActivityItem>>("/activities?state=done&limit=10") : none,
  ]);
  const today = dayOf(new Date().toISOString(), me.org.timezone);
  // "Due for you": what's overdue and what's due today.
  const due = mine.items.map((a) => followUpRow(a, today, me.org.timezone)).filter((f) => f.bucket === "overdue" || f.bucket === "today");
  const canAdd = can(me, "customers.create");

  return (
    <>
      <PageHeader
        title="Overview"
        actions={
          canAdd && (
            <LinkButton href="/companies/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add customer
            </LinkButton>
          )
        }
      >
        {me.role?.name}
        {me.team ? ` · Your team: ${me.team.name}` : ""}
      </PageHeader>

      <Sheet className="mb-5 grid grid-cols-2 divide-rule sm:grid-cols-5 sm:divide-x [&>*:nth-child(n+3)]:border-t [&>*:nth-child(n+3)]:border-rule sm:[&>*:nth-child(n+3)]:border-t-0">
        <Figure label="Customers" value={companies.total} href="/companies" />
        <Figure label="Prospects" value={prospects.total} href="/companies?status=prospect" />
        <Figure label="Overdue for you" value={counts.overdue} flag href="/follow-ups" />
        <Figure label="Due today for you" value={counts.today} href="/follow-ups" />
        <Figure label="Coming up for you" value={counts.upcoming} href="/follow-ups" />
      </Sheet>

      <div className="grid gap-5 lg:grid-cols-2">
        <Sheet className="px-5 pt-4 pb-2">
          <SectionTitle
            icon="followUps"
            action={
              <Link href="/follow-ups" className="text-meta font-medium text-hema hover:underline">
                All follow-ups
              </Link>
            }
          >
            Due for you
          </SectionTitle>
          {due.length === 0 ? (
            <Empty icon="followUps" title="Nothing due today">Overdue and today&apos;s follow-ups show up here.</Empty>
          ) : (
            <ul className="divide-y divide-rule">
              {due.map((f) => (
                <FollowUpItem key={f.id} today={today} row={f} org={me.org} />
              ))}
            </ul>
          )}
        </Sheet>

        <Sheet className="px-5 pt-4 pb-2">
          <SectionTitle icon="activity">Recent activity</SectionTitle>
          {recent.items.length === 0 ? (
            <Empty icon="activity" title="No activity yet">Whatever your team logs against a customer shows up here.</Empty>
          ) : (
            <ul className="divide-y divide-rule">
              {recent.items.map((a) => {
                const kind = kindOf(a.kind);
                const customer = customerOf(a);
                return (
                  <li key={a.id} className="py-3">
                    <p className="text-meta text-ink-3">
                      <span className="inline-flex items-center gap-1 align-[-2px] font-semibold text-ink-2">
                        <Icon name={kind.icon} className="size-3.5" />
                        {kind.label}
                      </span>{" "}
                      · {fmt.whenLabel(a.at, today)} · {a.owner.name}
                    </p>
                    <p className="mt-0.5">
                      {customer.href ? (
                        <Link href={customer.href} className="font-medium text-hema hover:underline">
                          {customer.name}
                        </Link>
                      ) : null}
                      <span className="text-ink-2">
                        {customer.href ? " — " : ""}
                        {a.subject}
                      </span>
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </Sheet>
      </div>
    </>
  );
}
