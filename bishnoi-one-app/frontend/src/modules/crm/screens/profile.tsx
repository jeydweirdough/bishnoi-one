import { Activity, BadgeCheck, CalendarDays, CircleCheck, Gauge, Phone, Target, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Avatar } from "@/src/platform/ui/avatar";
import { LinkButton, buttonClass } from "@/src/platform/ui/button";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load, loadQuery } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { KpiScorecard } from "@/src/platform/lib/types";
import type { Account } from "@/src/platform/screens/account";
import type { Profile } from "@/src/modules/crm/actions/profile";
import { shiftMonth } from "@/src/modules/crm/components/field/words";
import { tally } from "@/src/modules/crm/components/kpis/performance";
import { STATUS } from "@/src/modules/crm/components/kpis/words";
import { ProgressRing } from "@/src/modules/crm/components/progress-ring";
import { HEAT_WEEKS, Heatmap, WeekBars, addDays, mondayOf } from "@/src/modules/crm/components/profile/activity";
import { PictureButton } from "@/src/modules/crm/components/profile/picture-button";
import { ProfileActions } from "@/src/modules/crm/components/profile/profile-actions";
import { Mine, Team, plural, ranked, standing } from "@/src/modules/crm/screens/performance";

export const metadata = { title: "Profile" };

// Who you are and how you're doing, on one page: the person at the top, then
// their month against their targets, the leaderboard (for whoever leads people,
// who already see everyone's results), and what they got done day by day.
// Performance lives here now: a lead's team results are the "My team" tab;
// setting targets keeps its own page (/performance/targets).

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
const TONE = { green: "good", amber: "warn", red: "bad" } as const;
const BASE = "/crm/account";

export default async function ProfilePage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const params = await searchParams;
  const fmt = makeFormat(me.org);
  const today = fmt.todayKey();
  const thisMonth = today.slice(0, 7);
  // Who sees everyone's results: the same people the old Performance page showed them to.
  const teamWide = me.role?.scope !== "own" && (can(me, "goals.view") || can(me, "reports.view"));
  const tab = one(params.tab) === "team" && teamWide ? "team" : "me";
  const month = /^\d{4}-\d{2}$/.test(one(params.month)) ? one(params.month) : thisMonth;
  const [account, profile] = await Promise.all([load<Account>("/auth/account").catch(() => null), load<Profile>("/auth/profile")]);

  return (
    <>
      <Hero me={me} account={account} profile={profile} today={today} />
      {teamWide && (
        <div className="mb-5">
          <ToggleLinks
            current={tab}
            options={[
              { value: "me", label: "Overview", href: BASE },
              { value: "team", label: me.role?.scope === "all" ? "Everyone" : "My team", href: `${BASE}?tab=team` },
            ]}
          />
        </div>
      )}
      {tab === "team" ? (
        <TeamTab params={params} month={month} fmt={fmt} />
      ) : (
        <Overview me={me} params={params} month={month} today={today} fmt={fmt} teamWide={teamWide} />
      )}
    </>
  );
}

/** The person: a band, their picture, name, email, when they joined, their role and team. */
function Hero({ me, account, profile, today }: { me: Awaited<ReturnType<typeof getCompanyMe>>; account: Account | null; profile: Profile; today: string }) {
  const joined = account ? new Intl.DateTimeFormat(me.org.locale, { dateStyle: "medium", timeZone: me.org.timezone }).format(new Date(account.memberSince)) : null;
  // Their main team first, then the others they're in.
  const team = [account?.team?.name ?? me.team?.name, ...(me.otherTeams ?? []).map((t) => t.name)].filter(Boolean).join(", ") || null;
  const role = account?.role.name ?? me.role?.name ?? null;
  return (
    <Sheet className="mb-4 overflow-hidden">
      <div className="h-24 bg-gradient-to-r from-sage-deep via-sage to-mint sm:h-32" aria-hidden />
      <div className="px-5 pb-5 sm:px-6">
        <div className="-mt-10 flex flex-wrap items-end justify-between gap-3">
          <span className="relative">
            <Avatar name={me.user.fullName} id={me.user.id} photoAt={me.user.photoAt} size="xl" className="ring-4 ring-sheet" />
            <PictureButton name={me.user.fullName} id={me.user.id} photoAt={me.user.photoAt} />
          </span>
          <ProfileActions profile={profile} today={today} />
        </div>
        <h1 className="mt-3 text-[1.375rem] leading-tight font-semibold text-ink">{me.user.fullName}</h1>
        <p className="text-meta text-ink-3">{me.user.email}</p>
        <p className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-meta text-ink-2">
          {joined && (
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays className="size-3.5 text-ink-3" aria-hidden />
              Joined {joined}
            </span>
          )}
          {role && (
            <span className="inline-flex items-center gap-1.5">
              <BadgeCheck className="size-3.5 text-ink-3" aria-hidden />
              {role}
            </span>
          )}
          <span className="inline-flex items-center gap-1.5">
            <Users className="size-3.5 text-ink-3" aria-hidden />
            {team ?? "Not in a team"}
          </span>
          {profile.phone && (
            <span className="inline-flex items-center gap-1.5">
              <Phone className="size-3.5 text-ink-3" aria-hidden />
              {profile.phone}
            </span>
          )}
          <span className="text-ink-3">{me.org.name}</span>
        </p>
        {account?.role.description && <p className="mt-2 max-w-3xl text-sm text-ink-2">{account.role.description}</p>}
      </div>
    </Sheet>
  );
}

/** A figure on a green card, with its icon large and faint behind it. */
function StatCard({ icon, value, label, note }: { icon: ReactNode; value: string; label: string; note?: string }) {
  return (
    <div className="relative overflow-hidden rounded-xl bg-sage-deep px-5 py-4 text-white shadow-sheet">
      <span className="[&>svg]:size-5">{icon}</span>
      <p className="mt-3 text-[1.75rem] leading-tight font-semibold tabular-nums">{value}</p>
      <p className="text-sm text-white/85">{label}</p>
      {note && <p className="text-meta text-white/65">{note}</p>}
      <span className="pointer-events-none absolute -right-3 -bottom-4 text-white/10 [&>svg]:size-24" aria-hidden>
        {icon}
      </span>
    </div>
  );
}

async function Overview({
  me,
  params,
  month,
  today,
  fmt,
  teamWide,
}: {
  me: Awaited<ReturnType<typeof getCompanyMe>>;
  params: Record<string, string | string[] | undefined>;
  month: string;
  today: string;
  fmt: Format;
  teamWide: boolean;
}) {
  const thisMonth = today.slice(0, 7);
  const boardMonth = one(params.board) === "last" ? shiftMonth(thisMonth, -1) : thisMonth;
  const week = one(params.week) === "1" ? 1 : 0;
  const heatStart = addDays(mondayOf(today), -7 * (HEAT_WEEKS - 1));
  // One request for the month (and the two before it, for the table), and the leaderboard's.
  const [{ card, before, earlier, board }, daily] = await Promise.all([
    loadQuery<{ card: KpiScorecard; before?: KpiScorecard; earlier?: KpiScorecard; board?: KpiScorecard }>(
      `query Profile($month: String!, $before: String!, $earlier: String!, $board: String!, $wide: Boolean!) {
        card: performance(view: "mine", month: $month)
        before: performance(view: "mine", month: $before)
        earlier: performance(view: "mine", month: $earlier)
        board: performance(view: "team", month: $board) @include(if: $wide)
      }`,
      { month, before: shiftMonth(month, -1), earlier: shiftMonth(month, -2), board: boardMonth, wide: teamWide },
      ["card"],
    ),
    load<{ days: Record<string, number> }>(`/activities/daily?from=${heatStart}&to=${addDays(today, 1)}`).catch(() => ({ days: {} as Record<string, number> })),
  ]);
  const days = daily.days;
  const results = card.people[0]?.results ?? {};
  const measured = card.kpis.filter((k) => results[k.id]);
  const mine = standing(card, results);
  const t = tally(measured.map((k) => results[k.id]));
  const targeted = measured.length - t.none;
  const doneInMonth = Object.entries(days).reduce((sum, [k, n]) => (k.startsWith(month) ? sum + n : sum), 0);
  const monthName = `${fmt.monthLabel(month)} ${month.slice(0, 4)}`;
  // Keeps the other choices when one changes.
  const link = (change: Record<string, string>) => {
    const q = new URLSearchParams();
    for (const key of ["month", "board", "week"]) if (one(params[key])) q.set(key, one(params[key]));
    for (const [k, v] of Object.entries(change)) (v ? q.set(k, v) : q.delete(k));
    return q.size ? `${BASE}?${q}` : BASE;
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_21rem]">
      <div className="min-w-0 space-y-5">
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard icon={<Target aria-hidden />} value={mine.pct === null ? "—" : `${mine.pct}%`} label="Target attainment" note={mine.pct === null ? "No targets set yet" : monthName} />
          <StatCard icon={<CircleCheck aria-hidden />} value={targeted ? `${t.green} of ${targeted}` : "—"} label="Measures on target" note={targeted ? (t.red ? `${t.red} behind` : "None behind") : "No measures yet"} />
          <StatCard icon={<Activity aria-hidden />} value={String(doneInMonth)} label="Completed this month" note="Activities and visits" />
        </div>

        <section aria-labelledby="results">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h2 id="results" className="text-heading text-ink">
              Results · {monthName}
            </h2>
            <span className="ml-auto flex gap-1">
              <a href={link({ month: shiftMonth(month, -1) })} className={buttonClass("quiet", "sm")}>
                ‹ {fmt.monthLabel(shiftMonth(month, -1))}
              </a>
              {month !== thisMonth && (
                <a href={link({ month: "" })} className={buttonClass("quiet", "sm")}>
                  This month
                </a>
              )}
              {month < thisMonth && (
                <a href={link({ month: shiftMonth(month, 1) })} className={buttonClass("quiet", "sm")}>
                  {fmt.monthLabel(shiftMonth(month, 1))} ›
                </a>
              )}
            </span>
          </div>
          <Mine card={card} history={[before, earlier]} fmt={fmt} me={me} figures={false} />
        </section>

        {board && <Leaderboard board={board} meId={me.user.id} last={boardMonth !== thisMonth} link={link} fmt={fmt} />}
      </div>

      <aside className="space-y-5" aria-label="Monthly performance and activity">
        <Sheet className="px-5 py-5">
          <p className="text-caps text-ink-3 uppercase">{monthName}&apos;s targets</p>
          <div className="mt-3 flex items-center gap-4">
            <ProgressRing size="md" pct={mine.pct} pace={mine.pace} tone={mine.worst ? TONE[mine.worst] : "none"} label={mine.pct === null ? "No targets set" : `${mine.pct}% of your targets`} />
            <div className="min-w-0 text-sm">
              {mine.pct === null ? (
                <p className="text-ink-2">No targets set for you this month.</p>
              ) : (
                <>
                  <p className={`font-semibold ${mine.worst ? STATUS[mine.worst].text : "text-ink"}`}>{mine.worst ? STATUS[mine.worst].label : "On target"}</p>
                  {mine.pace !== null && month === thisMonth && <p className="text-meta text-ink-3">By today: {Math.round(mine.pace)}%</p>}
                </>
              )}
              {month === thisMonth && <p className="text-meta text-ink-3">{fmt.plural(daysLeft(today), "day")} left</p>}
            </div>
          </div>
          <LinkButton href={`/crm/performance/scorecards?month=${month}`} icon={<Gauge className="size-4" aria-hidden />} className="mt-4 w-full">
            Your scorecard
          </LinkButton>
          {card.canSetTargets && (
            <LinkButton href={`/crm/performance/targets?month=${month}`} icon={<Target className="size-4" aria-hidden />} className="mt-2 w-full">
              Set targets
            </LinkButton>
          )}
        </Sheet>
        <WeekBars days={days} today={today} week={week} base={link({ week: "" })} />
        <Heatmap days={days} today={today} />
      </aside>
    </div>
  );
}

/** Days left in the month, today included. */
function daysLeft(today: string): number {
  const [y, m, d] = today.split("-").map(Number);
  return new Date(Date.UTC(y, m, 0)).getUTCDate() - d + 1;
}

const PODIUM = [
  { at: 1, block: "h-20", avatar: "md" as const },
  { at: 0, block: "h-28", avatar: "lg" as const },
  { at: 2, block: "h-14", avatar: "md" as const },
];

/** Who's furthest towards their targets: the top three on a podium, everyone else in order under it. */
function Leaderboard({ board, meId, last, link, fmt }: { board: KpiScorecard; meId: string; last: boolean; link: (c: Record<string, string>) => string; fmt: Format }) {
  const rows = ranked(board);
  const placed = rows.filter((r) => r.pct !== null);
  const unplaced = rows.filter((r) => r.pct === null);
  const role = board.roles.find((r) => r.id === board.role)?.name;
  return (
    <Sheet className="px-5 pt-4 pb-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-heading text-ink">Leaderboard</h2>
          <p className="text-meta text-ink-3">
            {role ? plural(role) : "Everyone"} ranked by target attainment, {fmt.monthLabel(board.month)}.
          </p>
        </div>
        <ToggleLinks
          current={last ? "last" : "this"}
          options={[
            { value: "this", label: "This month", href: link({ board: "" }) },
            { value: "last", label: "Last month", href: link({ board: "last" }) },
          ]}
        />
      </div>
      {placed.length === 0 ? (
        <Empty compact icon="goals" title="No rankings yet">
          The leaderboard fills in once people have targets for the month.
        </Empty>
      ) : (
        <>
          <ol className="mx-auto mt-6 grid max-w-xl grid-cols-3 items-end gap-2 sm:gap-3" aria-label="Top three">
            {PODIUM.map(({ at, block, avatar }) => {
              const r = placed[at];
              if (!r) return <li key={at} aria-hidden />;
              return (
                <li key={at} className="flex min-w-0 flex-col items-center text-center">
                  <Avatar name={r.p.person.name} id={r.p.person.id} size={avatar} className={at === 0 ? "ring-4 ring-sage" : "ring-2 ring-mint-2"} />
                  <p className="mt-2 w-full truncate text-sm font-semibold text-ink">
                    {r.p.person.name}
                    {r.p.person.id === meId && <span className="font-normal text-ink-3"> (you)</span>}
                  </p>
                  <span className="mt-1 rounded-full bg-mint px-2.5 py-0.5 text-meta font-semibold text-sage-deep tabular-nums">{r.pct}%</span>
                  <span className={`mt-3 grid w-full place-items-center rounded-t-lg bg-gradient-to-b from-sage-deep to-filed text-[1.75rem] font-bold text-white ${block}`}>
                    <span className="sr-only">Place </span>
                    {at + 1}
                  </span>
                </li>
              );
            })}
          </ol>
          {(placed.length > 3 || unplaced.length > 0) && (
            <ol start={4} className="mt-5 divide-y divide-rule border-t border-rule">
              {placed.slice(3).map((r, i) => (
                <li key={r.p.person.id} className={`flex items-center gap-3 py-2.5 text-sm ${r.p.person.id === meId ? "bg-mint/60" : ""}`}>
                  <span className="w-6 text-right text-meta font-semibold text-ink-3 tabular-nums">{i + 4}</span>
                  <Avatar name={r.p.person.name} id={r.p.person.id} size="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-ink">{r.p.person.name}</span>
                    <span className="block truncate text-meta text-ink-3">{r.p.team?.name ?? "No team"}</span>
                  </span>
                  <span className="font-semibold text-ink tabular-nums">{r.pct}%</span>
                </li>
              ))}
              {unplaced.map((r) => (
                <li key={r.p.person.id} className="flex items-center gap-3 py-2.5 text-sm">
                  <span className="w-6 text-right text-meta text-ink-3">–</span>
                  <Avatar name={r.p.person.name} id={r.p.person.id} size="sm" />
                  <span className="min-w-0 flex-1 truncate text-ink-2">{r.p.person.name}</span>
                  <span className="text-meta text-ink-3">No target</span>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </Sheet>
  );
}

/** A lead's team, as the Performance page showed it: one role at a time, by person or by team. */
async function TeamTab({ params, month, fmt }: { params: Record<string, string | string[] | undefined>; month: string; fmt: Format }) {
  const role = one(params.role);
  const show = one(params.show) === "teams" ? "teams" : "people";
  const { card } = await loadQuery<{ card: KpiScorecard }>(
    `query Team($month: String!, $role: String) { card: performance(view: "team", month: $month, role: $role) }`,
    { month, ...(role ? { role } : {}) },
    ["card"],
  );
  const href = (m: string, r = card.role, s = show) => `${BASE}?tab=team&month=${m}${r ? `&role=${r}` : ""}${s === "teams" ? "&show=teams" : ""}`;
  const targets = `/crm/performance/targets?month=${card.month}`;
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h2 className="text-heading text-ink">
          {fmt.monthLabel(card.month)} {card.month.slice(0, 4)}
        </h2>
        {card.roles.length > 1 && (
          <ToggleLinks current={card.role ?? ""} options={card.roles.map((r) => ({ value: r.id, label: `${plural(r.name)} · ${r.people}`, href: href(card.month, r.id) }))} />
        )}
        <span className="ml-auto flex flex-wrap gap-1">
          <a href={href(shiftMonth(card.month, -1))} className={buttonClass("quiet", "sm")}>
            ‹ {fmt.monthLabel(shiftMonth(card.month, -1))}
          </a>
          {card.month !== card.thisMonth && (
            <a href={href(card.thisMonth)} className={buttonClass("quiet", "sm")}>
              This month
            </a>
          )}
          {card.month < card.thisMonth && (
            <a href={href(shiftMonth(card.month, 1))} className={buttonClass("quiet", "sm")}>
              {fmt.monthLabel(shiftMonth(card.month, 1))} ›
            </a>
          )}
          <LinkButton href={`/crm/performance/scorecards?month=${card.month}`} size="sm" icon={<Gauge className="size-4" aria-hidden />}>
            Scorecards
          </LinkButton>
          {card.canSetTargets && (
            <LinkButton href={targets} size="sm" icon={<Target className="size-4" aria-hidden />}>
              Set targets
            </LinkButton>
          )}
        </span>
      </div>
      <Team card={card} fmt={fmt} show={show} href={(s) => href(card.month, card.role, s)} targets={targets} />
    </>
  );
}
