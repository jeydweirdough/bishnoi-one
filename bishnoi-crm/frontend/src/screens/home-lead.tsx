import Link from "next/link";
import { FollowUpItem } from "../components/follow-up-item";
import { NewCustomerButton } from "../components/crm/new-customer";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { AttentionPanel } from "../components/attention-panel";
import { query } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { ActivityItem, Assignable, CompanyRow, Me, Org, Paged, PeopleInsights, PersonInsight, Quote, SalesResults } from "@/src/platform/lib/types";
import type { Figure } from "../components/deals/figure-card";
import { MonthCard, paceFigure } from "../components/kpis/performance";
import { customerOf, dayOf, followUpRow } from "../components/crm/follow-up-rows";
import { LogActivityButton } from "../components/crm/log-activity-button";
import { KINDS, kindOf } from "../components/crm/words";

/** What each person did this week, in words: "3 calls · 1 meeting". */
function didWords(p: PersonInsight): string {
  const parts = KINDS.filter((k) => p.doneByKind[k.kind]).map((k) => {
    const n = p.doneByKind[k.kind]!;
    return `${n} ${n === 1 ? k.label.toLowerCase() : `${k.label.toLowerCase()}s`}`;
  });
  return parts.join(" · ") || "Nothing logged";
}

function TeamTable({ people, fmt, today }: { people: PersonInsight[]; fmt: Format; today: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[52rem] text-sm">
        <thead>
          <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
            <th scope="col" className="py-2 pr-3 font-semibold">Person</th>
            <th scope="col" className="px-3 py-2 font-semibold">To do</th>
            <th scope="col" className="px-3 py-2 font-semibold">Completed this week</th>
            <th scope="col" className="px-3 py-2 text-right font-semibold">Customers</th>
            <th scope="col" className="px-3 py-2 text-right font-semibold">Quoted this month</th>
            <th scope="col" className="py-2 pl-3 text-right font-semibold">Last active</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {people.map((p) => (
            <tr key={p.id} className={p.overdue ? "bg-danger-tint/40" : ""}>
              <th scope="row" className="py-2.5 pr-3 text-left font-medium">
                <Link href={`/activities?who=team&person=${p.id}`} className="text-ink hover:underline">
                  {p.isMe ? "You" : p.name}
                </Link>
                <span className="block text-meta font-normal text-ink-3">{p.role}</span>
              </th>
              <td className="px-3 py-2.5">
                {p.overdue > 0 && <span className="font-semibold text-danger">{p.overdue} overdue</span>}
                {p.overdue > 0 && (p.dueToday > 0 || p.upcoming > 0) && <span className="text-ink-3"> · </span>}
                {p.dueToday > 0 && <span>{p.dueToday} today</span>}
                {p.dueToday > 0 && p.upcoming > 0 && <span className="text-ink-3"> · </span>}
                {p.upcoming > 0 && <span className="text-ink-2">{p.upcoming} coming up</span>}
                {!p.overdue && !p.dueToday && !p.upcoming && <span className="text-ink-3">None planned</span>}
              </td>
              <td className={`px-3 py-2.5 ${p.doneThisWeek ? "" : "text-ink-3"}`}>{didWords(p)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">
                {p.customers}
                {p.newCustomersThisMonth > 0 && <span className="block text-meta text-ink-3">+{p.newCustomersThisMonth} this month</span>}
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums">
                {p.quotesThisMonth ? fmt.peso(p.quotedThisMonthCentavos) : "—"}
                <span className="block text-meta text-ink-3">
                  {[
                    p.quotesThisMonth && `${p.quotesThisMonth} ${p.quotesThisMonth === 1 ? "quote" : "quotes"}`,
                    p.quotesWaiting && `${p.quotesWaiting} waiting`,
                    p.quotesRejectedThisMonth && `${p.quotesRejectedThisMonth} rejected`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </td>
              <td className="py-2.5 pl-3 text-right text-meta text-ink-2">{p.lastActivityAt ? fmt.whenLabel(p.lastActivityAt, today) : "Never"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A Team Lead's day starts with their team: who's behind, what got done, what's due, what waits on them. */
export async function LeadHome({ me }: { me: Me & { org: Org } }) {
  const fmt = makeFormat(me.org);
  const none: Paged<never> = { items: [], total: 0 };
  const approver = can(me, "quotes.approve");
  // Home's one request. The customers are for the "log a call" picker, so only their names.
  const { data } = await query<{
    insights: PeopleInsights | null;
    teamDue: Paged<ActivityItem> | null;
    teamDone: Paged<ActivityItem> | null;
    toApprove?: Paged<Quote> | null;
    people: Assignable[] | null;
    companies?: { items: Pick<CompanyRow, "id" | "name">[]; total: number } | null;
    results?: SalesResults | null;
  }>(
    `query LeadHome($approver: Boolean!, $customers: Boolean!, $sales: Boolean!) {
      insights: peopleInsights
      teamDue: activities(state: "open", limit: 200)
      teamDone: activities(state: "done", limit: 10)
      toApprove: quotes(task: "approvals", limit: 5) @include(if: $approver)
      results: salesResults(view: "team") @include(if: $sales)
      people { id name isMe team { id name } }
      companies(limit: 200) @include(if: $customers) { total items { id name } }
    }`,
    { approver, customers: can(me, "customers.view"), sales: can(me, "deals.view") && can(me, "reports.view") },
  );
  if (!data.insights) throw new Error("Home couldn't read how your team is doing.");
  const insights = data.insights;
  const teamDue = data.teamDue ?? none;
  const teamDone = data.teamDone ?? none;
  const toApprove = data.toApprove ?? none;
  const people = data.people ?? [];
  const companies = data.companies ?? none;
  const today = dayOf(new Date().toISOString(), me.org.timezone);
  const t = insights.totals;
  // Due now across the team, overdue first: each with whose it is.
  const due = teamDue.items
    .map((a) => followUpRow(a, today, me.org.timezone, { place: a.owner.id === me.user.id ? "You" : a.owner.name }))
    .filter((f) => f.bucket === "overdue" || f.bucket === "today")
    .sort((a, b) => (a.bucket === b.bucket ? a.dueOn.localeCompare(b.dueOn) : a.bucket === "overdue" ? -1 : 1));
  const others = insights.people.filter((p) => !p.isMe);
  // The team's month, each figure once: the revenue target leads; the rest are tiles.
  const r = data.results;
  const lead: Figure = r
    ? paceFigure({ value: fmt.peso(r.totals.wonCentavos), label: "Team revenue won", actual: r.totals.wonCentavos, target: r.totals.targetCentavos, start: r.start, end: r.end, today, show: fmt.peso, href: "/deals", noTarget: "No revenue target set for the team" })
    : { value: fmt.peso(t.quotedThisMonthCentavos), label: "Quoted by the team", note: fmt.plural(t.quotesThisMonth, "quote"), href: "/quotes" };
  const tiles: Figure[] = [
    { value: String(t.overdue), label: "Overdue", note: t.overdue ? "in the team: chase it" : "Nothing overdue", alert: t.overdue > 0, href: "/activities?who=team" },
    ...(approver ? [{ value: String(toApprove.total), label: "To approve", note: toApprove.total ? "quotes waiting on you" : "Nothing waiting", alert: toApprove.total > 0, href: "/quotes?task=approvals" }] : [{ value: String(t.newCustomersThisMonth), label: "New customers", note: "this month", href: "/companies" }]),
    ...(r ? [{ value: fmt.peso(t.quotedThisMonthCentavos), label: "Quoted", note: fmt.plural(t.quotesThisMonth, "quote"), href: "/quotes" }] : []),
    { value: String(t.doneThisWeek), label: "Completed this week", note: `${t.activeThisWeek} of ${t.people} people logged work`, href: "/activities?view=history&who=team" },
  ];

  return (
    <>
      <PageHeader
        title="Home"
        actions={
          <>
            {can(me, "customers.create") && (
<NewCustomerButton variant="default" />
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
        {fmt.greeting()}, {me.user.fullName.split(" ")[0]}. You lead {me.team?.name ?? "your team"}: {others.length}{" "}
        {others.length === 1 ? "person" : "people"}.
      </PageHeader>
      <AttentionPanel />

      {/* What waits on the lead first, widest; beside it, the team's month in one card. */}
      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col gap-5">
          {approver && toApprove.total > 0 && (
            <Sheet className="px-5 pt-4 pb-2">
              <SectionTitle
                icon="quotes"
                action={
                  <Link href="/quotes?task=approvals" className="text-meta font-medium text-ink hover:underline">
                    All {toApprove.total} waiting
                  </Link>
                }
              >
                Waiting for your approval
              </SectionTitle>
              <ul className="divide-y divide-rule">
                {toApprove.items.map((q) => (
                  <li key={q.id} className="flex items-center justify-between gap-3 py-2.5">
                    <span className="min-w-0">
                      <Link href={`/quotes/${q.id}`} className="font-medium text-ink hover:underline">
                        {q.number}
                      </Link>
                      <span className="block truncate text-meta text-ink-3">
                        {q.customerName} · by {q.createdBy.name}
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-3">
                      <span className="text-sm tabular-nums">{fmt.peso(q.totalCentavos)}</span>
                      <Link href={`/quotes/${q.id}`} className="rounded-md border border-ink px-3 py-1 text-meta font-medium text-ink hover:bg-mint">
                        Review
                      </Link>
                    </span>
                  </li>
                ))}
              </ul>
            </Sheet>
          )}
          <Sheet className="flex-1 px-5 pt-4 pb-2">
            <SectionTitle
              icon="followUps"
              action={
                <Link href="/activities?who=team" className="text-meta font-medium text-ink hover:underline">
                  All team to do
                </Link>
              }
            >
              Due in the team
            </SectionTitle>
            {due.length === 0 ? (
              <Empty icon="followUps" title="No items due today">Overdue and today&apos;s meetings and tasks across the team show up here.</Empty>
            ) : (
              <ul className="divide-y divide-rule">
                {due.slice(0, 12).map((f) => (
                  <FollowUpItem key={f.id} today={today} row={f} org={me.org} />
                ))}
              </ul>
            )}
          </Sheet>
        </div>
        <div className="flex flex-col">
          <MonthCard
            title="Team performance this month"
            subtitle={`${fmt.monthLabel(today.slice(0, 7))} to date · ${me.team?.name ?? "your team"}`}
            action={can(me, "goals.view") ? { href: "/performance", label: "View performance" } : undefined}
            lead={lead}
            rest={tiles}
          />
        </div>
      </div>

      {/* Then each person, and what the team did. */}
      <Sheet className="mb-5 px-5 pt-4 pb-2">
        <SectionTitle icon="teams">Team</SectionTitle>
        <p className="text-meta text-ink-3">Sorted by those furthest behind. Select a name to view their to do.</p>
        <TeamTable people={insights.people} fmt={fmt} today={today} />
      </Sheet>

      <Sheet className="px-5 pt-4 pb-2">
        <SectionTitle
          icon="activity"
          action={
            <Link href="/activities?view=history&who=team" className="text-meta font-medium text-ink hover:underline">
              All team history
            </Link>
          }
        >
          Team activity
        </SectionTitle>
        {teamDone.items.length === 0 ? (
          <Empty icon="activity" title="No activity yet" actions={can(me, "activities.create") && <LogActivityButton
                label="Log activity"
                org={me.org}
                now={new Date().toISOString()}
                people={people}
                companies={companies.items.map((c) => ({ id: c.id, name: c.name }))}
              />}>
            Calls, meetings, emails and notes your team logs show up here.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {teamDone.items.map((a) => {
              const kind = kindOf(a.kind);
              const customer = customerOf(a);
              return (
                <li key={a.id} className="py-3">
                  <p className="text-meta text-ink-3">
                    <span className="font-semibold text-ink-2">{a.owner.id === me.user.id ? "You" : a.owner.name}</span> ·{" "}
                    <span className="inline-flex items-center gap-1 align-[-2px]">
                      <Icon name={kind.icon} className="size-3.5" />
                      {kind.label}
                    </span>{" "}
                    · {fmt.whenLabel(a.doneAt ?? a.at, today)}
                  </p>
                  <p className="mt-0.5">
                    {customer.href && (
                      <Link href={customer.href} className="font-medium text-ink hover:underline">
                        {customer.name}
                      </Link>
                    )}
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
    </>
  );
}
