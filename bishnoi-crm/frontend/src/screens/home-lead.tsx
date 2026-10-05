import { Plus } from "lucide-react";
import Link from "next/link";
import { FollowUpItem } from "../components/follow-up-item";
import { LinkButton } from "@/src/platform/ui/button";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { load } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { ActivityItem, Assignable, CompanyRow, Me, Org, Paged, PeopleInsights, PersonInsight, Quote } from "@/src/platform/lib/types";
import { customerOf, dayOf, followUpRow } from "../components/crm/follow-up-rows";
import { LogActivityButton } from "../components/crm/log-activity-button";
import { MonthTarget } from "../components/deals/month-target";
import { KINDS, kindOf } from "../components/crm/words";
import { Stat, Stats } from "../components/stats";

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
            <th scope="col" className="px-3 py-2 font-semibold">Did this week</th>
            <th scope="col" className="px-3 py-2 text-right font-semibold">Customers</th>
            <th scope="col" className="px-3 py-2 text-right font-semibold">Quoted this month</th>
            <th scope="col" className="py-2 pl-3 text-right font-semibold">Last active</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {people.map((p) => (
            <tr key={p.id} className={p.overdue ? "bg-danger-tint/40" : ""}>
              <th scope="row" className="py-2.5 pr-3 text-left font-medium">
                <Link href={`/activities?who=team&person=${p.id}`} className="text-hema hover:underline">
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
                {!p.overdue && !p.dueToday && !p.upcoming && <span className="text-ink-3">Nothing planned</span>}
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
  const [insights, teamDue, teamDone, toApprove, people, companies] = await Promise.all([
    load<PeopleInsights>("/insights/people"),
    load<Paged<ActivityItem>>("/activities?state=open&limit=200"),
    load<Paged<ActivityItem>>("/activities?state=done&limit=10"),
    approver ? load<Paged<Quote>>("/quotes?task=approvals&limit=1") : none,
    load<Assignable[]>("/people/assignable"),
    can(me, "customers.view") ? load<Paged<CompanyRow>>("/companies?limit=200") : none,
  ]);
  const today = dayOf(new Date().toISOString(), me.org.timezone);
  const t = insights.totals;
  // Due now across the team, overdue first: each with whose it is.
  const due = teamDue.items
    .map((a) => followUpRow(a, today, me.org.timezone, { place: a.owner.id === me.user.id ? "You" : a.owner.name }))
    .filter((f) => f.bucket === "overdue" || f.bucket === "today")
    .sort((a, b) => (a.bucket === b.bucket ? a.dueOn.localeCompare(b.dueOn) : a.bucket === "overdue" ? -1 : 1));
  const others = insights.people.filter((p) => !p.isMe);

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
        {fmt.greeting()}, {me.user.fullName.split(" ")[0]}. You lead {me.team?.name ?? "your team"}: {others.length}{" "}
        {others.length === 1 ? "person" : "people"}.
      </PageHeader>

      <Stats>
        <Stat label="Overdue in the team" value={t.overdue} flag href="/activities?who=team" />
        <Stat label="Due today" value={t.dueToday} href="/activities?who=team" />
        <Stat label="Done this week" value={t.doneThisWeek} note={`${t.activeThisWeek} of ${t.people} people logged work`} href="/activities?view=history&who=team" />
        <Stat label="Quoted this month" value={fmt.peso(t.quotedThisMonthCentavos)} note={`${t.quotesThisMonth} ${t.quotesThisMonth === 1 ? "quote" : "quotes"}`} href="/quotes" />
        {approver && <Stat label="Waiting for your approval" value={toApprove.total} flag href="/quotes?task=approvals" />}
      </Stats>

      {can(me, "deals.view") && <MonthTarget view="team" fmt={fmt} today={today} mayTarget={can(me, "goals.manage")} />}

      <Sheet className="mb-5 px-5 pt-4 pb-2">
        <SectionTitle icon="teams">Your team</SectionTitle>
        <p className="text-meta text-ink-3">Who&apos;s behind comes first. Click a name for their to do.</p>
        <TeamTable people={insights.people} fmt={fmt} today={today} />
      </Sheet>

      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <Sheet className="px-5 pt-4 pb-2">
          <SectionTitle
            icon="followUps"
            action={
              <Link href="/activities?who=team" className="text-meta font-medium text-hema hover:underline">
                All team to do
              </Link>
            }
          >
            Due in the team
          </SectionTitle>
          {due.length === 0 ? (
            <Empty icon="followUps" title="Nothing due today">Overdue and today&apos;s meetings and tasks across the team show up here.</Empty>
          ) : (
            <ul className="divide-y divide-rule">
              {due.slice(0, 12).map((f) => (
                <FollowUpItem key={f.id} today={today} row={f} org={me.org} />
              ))}
            </ul>
          )}
        </Sheet>

        <Sheet className="px-5 pt-4 pb-2">
          <SectionTitle
            icon="activity"
            action={
              <Link href="/activities?view=history&who=team" className="text-meta font-medium text-hema hover:underline">
                All team history
              </Link>
            }
          >
            What the team did
          </SectionTitle>
          {teamDone.items.length === 0 ? (
            <Empty icon="activity" title="Nothing logged yet" actions={can(me, "activities.create") && <LogActivityButton
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
                        <Link href={customer.href} className="font-medium text-hema hover:underline">
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
      </div>
    </>
  );
}
