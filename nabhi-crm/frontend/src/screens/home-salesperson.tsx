import { Plus } from "lucide-react";
import Link from "next/link";
import { FollowUpItem } from "../components/follow-up-item";
import { LinkButton } from "@/src/platform/ui/button";
import { Icon } from "@/src/platform/ui/icons";
import { QuoteStateMark } from "@/src/platform/ui/marks";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { ActivityItem, ActivitySummary, Assignable, CompanyRow, Paged, Quote } from "@/src/platform/lib/types";
import { customerOf, dayOf, followUpRow } from "../components/crm/follow-up-rows";
import { LogActivityButton } from "../components/crm/log-activity-button";
import { MonthTarget } from "../components/deals/month-target";
import { kindOf } from "../components/crm/words";



/** Where the day starts: what's due, what needs a hand, and what just happened. */
export async function SalespersonHome() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const seesActivities = can(me, "activities.view");
  const seesQuotes = can(me, "quotes.view");
  const approver = can(me, "quotes.approve");
  const none: Paged<never> = { items: [], total: 0 };
  const [counts, mine, recent, myQuotes, toApprove, people, companies] = await Promise.all([
    seesActivities ? load<ActivitySummary>("/activities/summary?owner=me") : { overdue: 0, today: 0, upcoming: 0, open: 0 },
    seesActivities ? load<Paged<ActivityItem>>("/activities?owner=me&state=open&limit=100") : none,
    seesActivities ? load<Paged<ActivityItem>>("/activities?state=done&limit=8") : none,
    seesQuotes ? load<Paged<Quote>>("/quotes?owner=me&limit=6") : none,
    approver ? load<Paged<Quote>>("/quotes?task=approvals&limit=1") : none,
    can(me, "activities.create") ? load<Assignable[]>("/people/assignable") : ([] as Assignable[]),
    can(me, "activities.create") && can(me, "customers.view") ? load<Paged<CompanyRow>>("/companies?limit=200") : none,
  ]);
  const today = dayOf(new Date().toISOString(), me.org.timezone);
  // Due now: overdue first, then today. What's further ahead waits in Activities.
  const due = mine.items.map((a) => followUpRow(a, today, me.org.timezone)).filter((f) => f.bucket === "overdue" || f.bucket === "today");
  const needsHand = myQuotes.items.filter((q) => q.state !== "ready");

  return (
    <>
      <PageHeader
        title="Home"
        actions={
          <>
            {can(me, "customers.create") && (
              <LinkButton href="/companies/new" icon={<Plus className="size-4" aria-hidden />}>
                Add customer
              </LinkButton>
            )}
            {can(me, "activities.create") && (
              <LogActivityButton
                variant="primary"
                org={me.org}
                now={new Date().toISOString()}
                people={people}
                companies={companies.items.map((c) => ({ id: c.id, name: c.name }))}
              />
            )}
          </>
        }
      >
        {fmt.greeting()}, {me.user.fullName.split(" ")[0]}. {me.role?.name}
        {me.team ? ` · ${me.team.name}` : ""}
      </PageHeader>

      {can(me, "deals.view") && <MonthTarget view="mine" fmt={fmt} today={today} mayTarget={can(me, "goals.manage")} />}

      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <div className="space-y-5">
          {seesActivities && (
            <Sheet className="px-5 pt-4 pb-2">
              <SectionTitle
                icon="followUps"
                action={
                  <Link href="/activities" className="text-meta font-medium text-hema hover:underline">
                    All to do
                  </Link>
                }
              >
                Your to do
              </SectionTitle>
              <p className="text-meta text-ink-3">
                <span className={counts.overdue ? "font-semibold text-danger" : ""}>{counts.overdue} overdue</span> · {counts.today} today ·{" "}
                {counts.upcoming} coming up
              </p>
              {due.length === 0 ? (
                <Empty icon="followUps" title="Nothing due today" actions={can(me, "activities.create") && <LogActivityButton
                      label="Plan a follow-up"
                      org={me.org}
                      now={new Date().toISOString()}
                      people={people}
                      companies={companies.items.map((c) => ({ id: c.id, name: c.name }))}
                    />}>
                  {counts.upcoming ? `${counts.upcoming} coming up later. ` : ""}Meetings and tasks you plan show up here on the day.
                </Empty>
              ) : (
                <ul className="divide-y divide-rule">
                  {due.map((f) => (
                    <FollowUpItem key={f.id} today={today} row={f} org={me.org} />
                  ))}
                </ul>
              )}
            </Sheet>
          )}

          {seesQuotes && (
            <Sheet className="px-5 pt-4 pb-2">
              <SectionTitle
                icon="quotes"
                action={
                  <Link href="/quotes?owner=me" className="text-meta font-medium text-hema hover:underline">
                    All your quotes
                  </Link>
                }
              >
                Your quotes
              </SectionTitle>
              {approver && toApprove.total > 0 && (
                <Link href="/quotes?task=approvals" className="mt-1 flex items-center justify-between rounded-[3px] bg-hema-tint px-3 py-2 text-sm font-medium text-hema hover:underline">
                  {toApprove.total} {toApprove.total === 1 ? "quote is" : "quotes are"} waiting for your approval
                  <span aria-hidden>→</span>
                </Link>
              )}
              {needsHand.length === 0 ? (
                <p className="py-3 text-meta text-ink-3">{myQuotes.total ? "None waiting or rejected." : "No quotes yet. Make one from a customer's page."}</p>
              ) : (
                <ul className="divide-y divide-rule">
                  {needsHand.map((q) => (
                    <li key={q.id} className="flex items-center justify-between gap-3 py-2.5">
                      <span className="min-w-0">
                        <Link href={`/quotes/${q.id}`} className="font-medium text-hema hover:underline">
                          {q.number}
                        </Link>
                        <span className="block truncate text-meta text-ink-3">{q.customerName}</span>
                      </span>
                      <span className="flex shrink-0 flex-col items-end gap-0.5">
                        <span className="text-sm tabular-nums">{fmt.peso(q.totalCentavos)}</span>
                        <QuoteStateMark state={q.state} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Sheet>
          )}
        </div>

        <Sheet className="px-5 pt-4 pb-2">
          <SectionTitle
            icon="activity"
            action={
              seesActivities && (
                <Link href="/activities?view=history" className="text-meta font-medium text-hema hover:underline">
                  All history
                </Link>
              )
            }
          >
            Recent activity
          </SectionTitle>
          {recent.items.length === 0 ? (
            <Empty icon="activity" title="No activity yet" actions={can(me, "activities.create") && <LogActivityButton
                  label="Log activity"
                  org={me.org}
                  now={new Date().toISOString()}
                  people={people}
                  companies={companies.items.map((c) => ({ id: c.id, name: c.name }))}
                />}>
              Whatever your team logs against a customer shows up here.
            </Empty>
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
