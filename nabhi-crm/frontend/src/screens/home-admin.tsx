import Link from "next/link";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Me, Org, PeopleInsights, PersonInsight } from "@/src/platform/lib/types";
import { dayOf } from "../components/crm/follow-up-rows";
import { Stat, Stats } from "../components/stats";

type TeamRow = { name: string; people: number; active: number; overdue: number; done: number; customers: number; quoted: number; quotes: number };

/** The same numbers, added up per team. */
function byTeam(people: PersonInsight[]): TeamRow[] {
  const teams = new Map<string, TeamRow>();
  for (const p of people) {
    const name = p.team?.name ?? "No team";
    const t = teams.get(name) ?? { name, people: 0, active: 0, overdue: 0, done: 0, customers: 0, quoted: 0, quotes: 0 };
    t.people += 1;
    t.active += p.doneThisWeek > 0 ? 1 : 0;
    t.overdue += p.overdue;
    t.done += p.doneThisWeek;
    t.customers += p.customers;
    t.quoted += p.quotedThisMonthCentavos;
    t.quotes += p.quotesThisMonth;
    teams.set(name, t);
  }
  return [...teams.values()].sort((a, b) => (a.name === "No team" ? 1 : b.name === "No team" ? -1 : a.name.localeCompare(b.name)));
}

/** The Administrator's first page: how the people are using the CRM, not the customers themselves. */
export async function AdminDashboard({ me }: { me: Me & { org: Org } }) {
  const fmt = makeFormat(me.org);
  const data = await load<PeopleInsights>("/insights/people");
  const today = dayOf(new Date().toISOString(), me.org.timezone);
  const t = data.totals;
  const people = [...data.people].filter((p) => !p.isMe).sort((a, b) => a.name.localeCompare(b.name));
  const teams = byTeam(people);
  const quiet = people.filter((p) => !p.signInsThisWeek);

  return (
    <>
      <PageHeader title="Dashboard">How your people are using Nabhi CRM: who signs in, who logs their work, and where work is piling up.</PageHeader>

      <Stats>
        <Stat label="Signed in this week" value={`${t.signedInThisWeek - (data.people.find((p) => p.isMe)?.signInsThisWeek ? 1 : 0)} of ${people.length}`} href="/admin/users" />
        <Stat label="Logged work this week" value={`${people.filter((p) => p.doneThisWeek).length} of ${people.length}`} note={`${t.doneThisWeek} activities`} />
        <Stat label="Overdue tasks" value={t.overdue} flag />
        <Stat label="Quoted this month" value={fmt.peso(t.quotedThisMonthCentavos)} note={`${t.quotesThisMonth} quotes · ${t.quotesWaiting} waiting`} />
        <Stat label="New customers this month" value={t.newCustomersThisMonth} note={`${t.customers} in all`} />
      </Stats>

      {quiet.length > 0 && (
        <p className="mb-5 rounded-[3px] bg-bench px-4 py-2.5 text-meta text-ink-2">
          Not signed in this week: {quiet.map((p) => p.name).join(", ")}.
        </p>
      )}

      <Sheet className="mb-5 px-5 pt-4 pb-2">
        <SectionTitle icon="teams">By team</SectionTitle>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                <th scope="col" className="py-2 pr-3 font-semibold">Team</th>
                <th scope="col" className="px-3 py-2 text-right font-semibold">Active this week</th>
                <th scope="col" className="px-3 py-2 text-right font-semibold">Activities</th>
                <th scope="col" className="px-3 py-2 text-right font-semibold">Overdue</th>
                <th scope="col" className="px-3 py-2 text-right font-semibold">Customers</th>
                <th scope="col" className="py-2 pl-3 text-right font-semibold">Quoted this month</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule tabular-nums">
              {teams.map((t) => (
                <tr key={t.name}>
                  <th scope="row" className="py-2.5 pr-3 text-left font-medium">{t.name}</th>
                  <td className="px-3 py-2.5 text-right">
                    {t.active} of {t.people}
                  </td>
                  <td className="px-3 py-2.5 text-right">{t.done}</td>
                  <td className={`px-3 py-2.5 text-right ${t.overdue ? "font-semibold text-danger" : ""}`}>{t.overdue}</td>
                  <td className="px-3 py-2.5 text-right">{t.customers}</td>
                  <td className="py-2.5 pl-3 text-right">
                    {t.quotes ? fmt.peso(t.quoted) : "—"}
                    {t.quotes > 0 && <span className="block text-meta text-ink-3">{t.quotes} quotes</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-2">
        <SectionTitle icon="people">By person</SectionTitle>
        {people.length === 0 ? (
          <Empty icon="people" title="Nobody else yet">Add people under People &amp; access.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[52rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th scope="col" className="py-2 pr-3 font-semibold">Person</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Last signed in</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Activities this week</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Overdue</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Customers</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Quotes this month</th>
                  <th scope="col" className="py-2 pl-3 font-semibold">Last activity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule tabular-nums">
                {people.map((p) => (
                  <tr key={p.id}>
                    <th scope="row" className="py-2.5 pr-3 text-left font-medium">
                      <Link href={`/admin/users/${p.id}`} className="text-hema hover:underline">
                        {p.name}
                      </Link>
                      <span className="block text-meta font-normal text-ink-3">{[p.role, p.team?.name].filter(Boolean).join(" · ")}</span>
                    </th>
                    <td className={`px-3 py-2.5 ${p.signInsThisWeek ? "" : "text-ink-3"}`}>{p.lastSignInAt ? fmt.whenLabel(p.lastSignInAt, today) : "Never"}</td>
                    <td className={`px-3 py-2.5 text-right ${p.doneThisWeek ? "" : "text-ink-3"}`}>{p.doneThisWeek}</td>
                    <td className={`px-3 py-2.5 text-right ${p.overdue ? "font-semibold text-danger" : "text-ink-3"}`}>{p.overdue}</td>
                    <td className="px-3 py-2.5 text-right">{p.customers}</td>
                    <td className="px-3 py-2.5 text-right">
                      {p.quotesThisMonth}
                      {p.quotesThisMonth > 0 && <span className="block text-meta text-ink-3">{fmt.peso(p.quotedThisMonthCentavos)}</span>}
                    </td>
                    <td className="py-2.5 pl-3 text-meta text-ink-2">{p.lastActivityAt ? fmt.whenLabel(p.lastActivityAt, today) : "Never"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Sheet>
    </>
  );
}
