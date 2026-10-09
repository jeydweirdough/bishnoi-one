import { Target } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Avatar } from "@/src/platform/ui/avatar";
import { LinkButton, buttonClass } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, loadQuery } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { KpiDef, KpiResult, KpiScorecard, Me, Org } from "@/src/platform/lib/types";
import { shiftMonth } from "../components/field/words";
import { StatusFigures, tally } from "../components/kpis/performance";
import { STATUS, kpiValue } from "../components/kpis/words";
import { ProgressRing } from "../components/progress-ring";

export const metadata = { title: "Performance" };

/** "Salesperson" → "Salespeople", "Field agent" → "Field agents": a role's tab. */
const plural = (role: string) => (/person$/i.test(role) ? role.replace(/person$/i, "people") : /s$/i.test(role) ? role : `${role}s`);
const TONE = { green: "good", amber: "warn", red: "bad", none: "none", waiting: "none" } as const;
// The status bars' colours: the checked palette, not the status tokens (a chart needs hex).
const STATUS_COLOR: Record<"green" | "amber" | "red" | "none", string> = { green: "#1a8a52", amber: "#eda100", red: "#e34948", none: "#d5d9df" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

/** Where the pages are: a lead's in the menu, an administrator's in Settings. */
export type Place = { results: string; targets: string; tabs?: ReactNode };
export const IN_MENU: Place = { results: "/performance", targets: "/performance/targets" };

// The month's results against their targets. A salesperson's own breakdown
// (their dashboard has the month's cards): each measure, where it should be by
// today, and the two months before. A lead's or administrator's: one role at a
// time, the statuses, a bar per person, a ring per measure, then the table.
export default async function PerformancePage({ searchParams, place = IN_MENU }: { searchParams: Search; place?: Place }) {
  const me = await getCompanyMe();
  const params = await searchParams;
  const teamWide = me.role?.scope !== "own" && (can(me, "goals.view") || can(me, "reports.view"));
  const view = teamWide && one(params.who) !== "me" ? "team" : "mine";
  const fmt = makeFormat(me.org);
  const month = /^\d{4}-\d{2}$/.test(one(params.month)) ? one(params.month) : fmt.todayKey().slice(0, 7);
  const role = one(params.role);
  const show = one(params.show) === "teams" ? "teams" : "people";
  // One request: the month, and for one's own breakdown the two months before.
  const { card, before, earlier } = await loadQuery<{ card: KpiScorecard; before?: KpiScorecard; earlier?: KpiScorecard }>(
    `query Performance($view: String!, $month: String!, $role: String, $before: String!, $earlier: String!, $mine: Boolean!) {
      card: performance(view: $view, month: $month, role: $role)
      before: performance(view: "mine", month: $before) @include(if: $mine)
      earlier: performance(view: "mine", month: $earlier) @include(if: $mine)
    }`,
    { view, month, ...(view === "team" && role ? { role } : {}), before: shiftMonth(month, -1), earlier: shiftMonth(month, -2), mine: view === "mine" },
    ["card"],
  );
  const href = (m: string, who = view, r = card.role, s = show) =>
    `${place.results}?month=${m}${who === "mine" && teamWide ? "&who=me" : ""}${who === "team" && r ? `&role=${r}` : ""}${who === "team" && s === "teams" ? "&show=teams" : ""}`;
  const name = `${fmt.monthLabel(card.month)} ${card.month.slice(0, 4)}`;

  return (
    <>
      <PageHeader
        title={view === "mine" ? "Your performance" : "Performance"}
        crumbs={view === "mine" && !teamWide ? [{ href: "/", label: "Home" }] : undefined}
        actions={
          card.canSetTargets && (
            <LinkButton href={`${place.targets}?month=${card.month}`} icon={<Target className="size-4" aria-hidden />}>
              Set targets
            </LinkButton>
          )
        }
      >
        {name}: results against targets.{card.month === card.thisMonth ? " Counts and amounts are judged against where they should be by today." : ""}
      </PageHeader>
      {place.tabs}

      {/* One row of choices: whose, which role, which month. */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {teamWide && (
          <ToggleLinks
            current={view}
            options={[
              { value: "mine", label: "Mine", href: href(card.month, "mine") },
              { value: "team", label: me.role?.scope === "all" ? "Everyone" : "My team", href: href(card.month, "team") },
            ]}
          />
        )}
        {view === "team" && card.roles.length > 1 && (
          <ToggleLinks current={card.role ?? ""} options={card.roles.map((r) => ({ value: r.id, label: `${plural(r.name)} · ${r.people}`, href: href(card.month, "team", r.id) }))} />
        )}
        <span className="ml-auto flex gap-1">
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
        </span>
      </div>

      {view === "mine" ? (
        <Mine card={card} history={[before, earlier]} fmt={fmt} me={me} />
      ) : (
        <Team card={card} fmt={fmt} show={show} href={(s) => href(card.month, "team", card.role, s)} targets={`${place.targets}?month=${card.month}`} />
      )}
    </>
  );
}

function NothingMeasured({ title, me }: { title: string; me: Me }) {
  return (
    <Sheet className="px-5 py-2">
      <Empty
        icon="goals"
        art="gauge"
        title={title}
        actions={
          can(me, "admin.settings") && (
            <LinkButton href="/admin/settings/performance" variant="primary">
              Choose what&apos;s measured
            </LinkButton>
          )
        }
      >
        An administrator chooses what each role is measured by under Settings → Performance.
      </Empty>
    </Sheet>
  );
}

/** One's own breakdown: the statuses, then each measure with where it should be by today and the two months before. */
function Mine({ card, history, fmt, me }: { card: KpiScorecard; history: (KpiScorecard | undefined)[]; fmt: Format; me: Me & { org: Org } }) {
  const results = card.people[0]?.results ?? {};
  const mine = card.kpis.filter((k) => results[k.id]);
  if (!mine.length) return <NothingMeasured title="Nothing is measured for your role yet" me={me} />;
  const past = history.filter((h): h is KpiScorecard => !!h);
  return (
    <>
      <StatusFigures results={mine.map((k) => results[k.id])} />
      <Sheet className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-meta text-ink-3">
              <th className="px-5 py-2 font-medium">Measured by</th>
              <th className="px-3 py-2 text-right font-medium">{fmt.monthLabel(card.month)}</th>
              <th className="px-3 py-2 text-right font-medium">By today</th>
              {past.map((h) => (
                <th key={h.month} className="px-3 py-2 text-right font-medium">
                  {fmt.monthLabel(h.month)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {mine.map((k) => {
              const r = results[k.id];
              return (
                <tr key={k.id}>
                  <td className="px-5 py-2.5">
                    <span className="block font-medium text-ink">{k.name}</span>
                    <span className="block text-meta text-ink-3">{k.description ?? k.measureLabel}{k.better === "lower" ? " · lower is better" : ""}</span>
                  </td>
                  <Cell kpi={k} r={r} fmt={fmt} />
                  <td className="px-3 py-2.5 text-right text-ink-2 tabular-nums">{r.expected !== null && r.target !== null ? kpiValue(k.unit, r.expected, fmt) : "—"}</td>
                  {past.map((h) => (
                    <Cell key={h.month} kpi={k} r={h.people[0]?.results[k.id]} fmt={fmt} />
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
        <Note>&quot;By today&quot; is the target spread over the month so far: where a count or an amount should be by now.</Note>
      </Sheet>
    </>
  );
}

function Cell({ kpi, r, fmt }: { kpi: KpiDef; r: KpiResult | undefined; fmt: Format }) {
  if (!r) return <td className="px-3 py-2.5 text-right text-ink-3">—</td>;
  const s = STATUS[r.status];
  const pace = r.target && r.expected !== null && r.expected !== r.target && kpi.better === "higher" ? (100 * r.expected) / r.target : null;
  return (
    <td className="px-3 py-2" title={s.label}>
      <span className="flex items-center justify-end gap-2.5">
        <span className="text-right whitespace-nowrap">
          <span className="block font-semibold text-ink tabular-nums">{kpiValue(kpi.unit, r.actual, fmt)}</span>
          <span className="block text-meta text-ink-3">{r.target !== null ? `of ${kpiValue(kpi.unit, r.target, fmt)}${r.ownTarget === false ? " (people's)" : ""}` : "No target"}</span>
          {r.target !== null && <span className={`block text-meta font-semibold ${s.text}`}>{s.label}</span>}
        </span>
        {r.target !== null && (
          <ProgressRing size="xs" pct={r.attainment} pace={pace} tone={TONE[r.status]} label={`${kpi.name}: ${kpiValue(kpi.unit, r.actual, fmt)} of ${kpiValue(kpi.unit, r.target, fmt)}, ${s.label.toLowerCase()}`} />
        )}
      </span>
    </td>
  );
}

/** One measure for the whole group: its total against the target, and how many people are where. */
function Overview({ kpi, total, results, fmt }: { kpi: KpiDef; total: KpiResult | undefined; results: KpiResult[]; fmt: Format }) {
  const t = tally(results);
  const s = total ? STATUS[total.status] : STATUS.none;
  const pace = total?.target && total.expected !== null && total.expected !== total.target && kpi.better === "higher" ? (100 * total.expected) / total.target : null;
  return (
    <Sheet className="px-5 py-4">
      <p className="text-caps text-ink-3 uppercase">{kpi.name}</p>
      <div className="mt-2 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[1.5rem] leading-tight font-semibold text-ink tabular-nums">{kpiValue(kpi.unit, total?.actual, fmt)}</p>
          <p className="text-meta text-ink-3">{total?.target ? `of ${kpiValue(kpi.unit, total.target, fmt)}` : "No targets set"}</p>
          {total?.target ? <p className={`mt-1 text-meta font-semibold ${s.text}`}>{s.label}</p> : null}
          <p className="mt-1 text-meta text-ink-3">
            {t.green} on target · {t.red} behind
          </p>
        </div>
        <ProgressRing
          size="sm"
          pct={total?.target ? total.attainment : null}
          pace={pace}
          tone={total?.target ? TONE[total.status] : "none"}
          label={`${kpi.name}, everyone: ${kpiValue(kpi.unit, total?.actual, fmt)}${total?.target ? ` of ${kpiValue(kpi.unit, total.target, fmt)}` : ""}`}
        />
      </div>
    </Sheet>
  );
}

/** How far each person is towards their targets: one bar each, best first, with where they should be by today. */
function ByPerson({ card, fmt }: { card: KpiScorecard; fmt: Format }) {
  const rows = card.people
    .map((p) => {
      const targeted = card.kpis.map((k) => p.results[k.id]).filter((r): r is KpiResult => !!r && r.target !== null && r.attainment !== null);
      const pct = targeted.length ? Math.round(targeted.reduce((s, r) => s + r.attainment!, 0) / targeted.length) : null;
      const paces = targeted.filter((r) => r.expected !== null && r.target).map((r) => (100 * r.expected!) / r.target!);
      const pace = paces.length ? paces.reduce((a, b) => a + b, 0) / paces.length : null;
      const worst = (["red", "amber", "green"] as const).find((s) => targeted.some((r) => r.status === s)) ?? null;
      return { p, pct, pace, worst, count: targeted.length };
    })
    .sort((a, b) => (b.pct ?? -1) - (a.pct ?? -1) || a.p.person.name.localeCompare(b.p.person.name));
  const several = card.kpis.length > 1;
  return (
    <Sheet className="px-5 py-4">
      <p className="text-caps text-ink-3 uppercase">Progress by person</p>
      <p className="mt-1 mb-3 text-meta text-ink-3">
        {several ? "The average of each person's measures with a target, " : `${card.kpis[0]?.name ?? "The measure"} `}against 100% of target. The dark tick: where they should be by today.
      </p>
      <ul className="space-y-2.5">
        {rows.map(({ p, pct, pace, worst, count }) => (
          <li key={p.person.id} className="grid grid-cols-[10rem_minmax(0,1fr)_3.5rem] items-center gap-3 text-sm">
            <span className="flex min-w-0 items-center gap-2">
              <Avatar name={p.person.name} id={p.person.id} size="sm" />
              <span className="truncate text-ink-2">{p.person.name}</span>
            </span>
            {pct === null ? (
              <span className="text-meta text-ink-3">No target</span>
            ) : (
              <span className="relative h-2.5 rounded-full bg-mint-2" role="img" aria-label={`${p.person.name}: ${pct}% of target${worst ? `, ${STATUS[worst].label.toLowerCase()}` : ""}`}>
                <span className="block h-full rounded-full" style={{ width: `${Math.min(100, pct)}%`, background: worst ? STATUS_COLOR[worst] : STATUS_COLOR.none }} />
                {pace !== null && pace < 100 && <span className="absolute -top-1 h-4.5 w-0.5 rounded bg-ink" style={{ left: `calc(${pace}% - 1px)` }} aria-hidden />}
              </span>
            )}
            <span className="text-right font-semibold text-ink tabular-nums" title={several && count ? `Average of ${fmt.plural(count, "measure")}` : undefined}>
              {pct === null ? "—" : `${pct}%`}
            </span>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}

function Team({ card, fmt, show, href, targets }: { card: KpiScorecard; fmt: Format; show: "people" | "teams"; href: (show: string) => string; targets: string }) {
  if (!card.people.length)
    return (
      <Sheet className="px-5 py-2">
        <Empty icon="goals" art="gauge" title="Nothing is measured for anyone in reach yet">
          An administrator chooses what each role is measured by under Settings → Performance.
        </Empty>
      </Sheet>
    );
  const all = card.people.flatMap((p) => card.kpis.map((k) => p.results[k.id]).filter((r): r is KpiResult => !!r));
  return (
    <>
      <StatusFigures results={all} targetsHref={card.canSetTargets ? targets : undefined} />

      <div className="mb-5 grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <ByPerson card={card} fmt={fmt} />
        <div className="grid content-start gap-3 md:grid-cols-2">
          {card.kpis.map((k) => (
            <Overview key={k.id} kpi={k} total={card.totals[k.id]} results={card.people.map((p) => p.results[k.id]).filter((r): r is KpiResult => !!r)} fmt={fmt} />
          ))}
        </div>
      </div>

      <Sheet className="overflow-x-auto">
        <div className="flex flex-wrap items-center gap-3 border-b border-rule px-5 py-3">
          <h2 className="text-heading text-ink">This month, by {show === "teams" ? "team" : "person"}</h2>
          <span className="ml-auto">
            <ToggleLinks
              current={show}
              options={[
                { value: "people", label: "People", href: href("people") },
                { value: "teams", label: "Teams", href: href("teams") },
              ]}
            />
          </span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-meta text-ink-3">
              <th className="px-5 py-2 font-medium">{show === "teams" ? "Team" : "Person"}</th>
              {card.kpis.map((k) => (
                <th key={k.id} className="px-3 py-2 text-right font-medium" title={k.description ?? undefined}>
                  {k.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {show === "people"
              ? card.people.map((p) => (
                  <tr key={p.person.id} className="hover:bg-bench/40">
                    <td className="px-5 py-2.5">
                      <Link href={`/admin/users/${p.person.id}`} className="flex items-center gap-2.5">
                        <Avatar name={p.person.name} id={p.person.id} size="sm" />
                        <span className="min-w-0">
                          <span className="block font-medium text-ink">{p.person.name}</span>
                          <span className="block text-meta text-ink-3">{p.team?.name ?? "No team"}</span>
                        </span>
                      </Link>
                    </td>
                    {card.kpis.map((k) => (
                      <Cell key={k.id} kpi={k} r={p.results[k.id]} fmt={fmt} />
                    ))}
                  </tr>
                ))
              : (
                  <>
                    {card.teams.map((tm) => (
                      <tr key={tm.team?.id ?? "none"}>
                        <td className="px-5 py-2.5 font-medium text-ink">{tm.team?.name ?? "No team"}</td>
                        {card.kpis.map((k) => (
                          <Cell key={k.id} kpi={k} r={tm.results[k.id]} fmt={fmt} />
                        ))}
                      </tr>
                    ))}
                    {card.teams.length > 1 && (
                      <tr className="border-t border-rule-strong">
                        <td className="px-5 py-2.5 font-semibold text-ink">Total</td>
                        {card.kpis.map((k) => (
                          <Cell key={k.id} kpi={k} r={card.totals[k.id]} fmt={fmt} />
                        ))}
                      </tr>
                    )}
                  </>
                )}
          </tbody>
        </table>
        {show === "teams" && <Note>A team&apos;s target is its own, or its people&apos;s added up (marked &quot;people&apos;s&quot;).</Note>}
      </Sheet>
    </>
  );
}

const Note = ({ children }: { children: ReactNode }) => <p className="border-t border-rule px-5 py-2.5 text-meta text-ink-3">{children}</p>;
