import { Target } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Avatar } from "@/src/platform/ui/avatar";
import { LinkButton, buttonClass } from "@/src/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { KpiDef, KpiResult, KpiScorecard, KpiStatus } from "@/src/platform/lib/types";
import { Donut } from "../components/deals/donut";
import { shiftMonth } from "../components/field/words";
import { STATUS, kpiValue } from "../components/kpis/words";
import { ProgressRing } from "../components/progress-ring";
import { Stat, Stats } from "../components/stats";

export const metadata = { title: "KPIs" };

/** "Salesperson" → "Salespeople", "Field agent" → "Field agents": a role's tab. */
const plural = (role: string) => (/person$/i.test(role) ? role.replace(/person$/i, "people") : /s$/i.test(role) ? role : `${role}s`);
const TONE = { green: "good", amber: "warn", red: "bad", none: "none", waiting: "none" } as const;
// The status chart's colours: the checked palette, not the status tokens (a chart needs hex).
const STATUS_COLOR: Record<"green" | "amber" | "red" | "none", string> = { green: "#1a8a52", amber: "#eda100", red: "#e34948", none: "#d5d9df" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

/** Where these results stand: how many on target, slightly behind, behind, without a target. */
function tally(results: KpiResult[]) {
  const n = (s: KpiStatus) => results.filter((r) => r.status === s).length;
  return { green: n("green"), amber: n("amber"), red: n("red"), none: results.filter((r) => r.target === null).length };
}

// The month's KPIs against their targets, laid out like the dashboard: four
// figures, then the progress (a bar per person, a ring per KPI, the statuses),
// then each person (or team) with a ring per KPI. One's own, or one role at a
// time for a lead.
export default async function KpisPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const params = await searchParams;
  const teamWide = me.role?.scope !== "own" && (can(me, "goals.view") || can(me, "reports.view"));
  const view = teamWide && one(params.who) !== "me" ? "team" : "mine";
  const asked = /^\d{4}-\d{2}$/.test(one(params.month)) ? one(params.month) : "";
  const role = one(params.role);
  const show = one(params.show) === "teams" ? "teams" : "people";
  const card = await load<KpiScorecard>(`/kpi-scorecard?view=${view}${asked ? `&month=${enc(asked)}` : ""}${view === "team" && role ? `&role=${enc(role)}` : ""}`);
  const fmt = makeFormat(me.org);
  const href = (month: string, who = view, r = card.role, s = show) =>
    `/kpis?month=${month}${who === "mine" && teamWide ? "&who=me" : ""}${who === "team" && r ? `&role=${r}` : ""}${who === "team" && s === "teams" ? "&show=teams" : ""}`;
  const name = `${fmt.monthLabel(card.month)} ${card.month.slice(0, 4)}`;

  return (
    <>
      <PageHeader
        title="KPIs"
        actions={
          card.canSetTargets && (
            <LinkButton href={`/kpis/targets?month=${card.month}`} icon={<Target className="size-4" aria-hidden />}>
              Set targets
            </LinkButton>
          )
        }
      >
        {name}: results against targets.{card.month === card.thisMonth ? " Counts and amounts are judged against where they should be by today." : ""}
      </PageHeader>

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
          <ToggleLinks
            current={card.role ?? ""}
            options={card.roles.map((r) => ({ value: r.id, label: `${plural(r.name)} · ${r.people}`, href: href(card.month, "team", r.id) }))}
          />
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

      {view === "mine" ? <Mine card={card} fmt={fmt} /> : <Team card={card} fmt={fmt} show={show} href={(s) => href(card.month, "team", card.role, s)} />}
    </>
  );
}

function NoKpis({ title }: { title: string }) {
  return (
    <Sheet className="px-5 py-2">
      <Empty icon="goals" title={title}>
        An administrator chooses the KPIs and who they&apos;re for under Settings → KPIs.
      </Empty>
    </Sheet>
  );
}

/** The four figures on top: where the results stand. */
function Figures({ results }: { results: KpiResult[] }) {
  const t = tally(results);
  const targeted = results.length - t.none;
  return (
    <Stats columns={4}>
      <Stat label="On target" value={t.green} note={targeted ? `of ${targeted} with a target` : "No targets set"} />
      <Stat label="Slightly behind" value={t.amber} />
      <Stat label="Behind" value={t.red} flag />
      <Stat label="Without a target" value={t.none} note={t.none ? "Set them under KPIs → Targets" : undefined} />
    </Stats>
  );
}

function Mine({ card, fmt }: { card: KpiScorecard; fmt: Format }) {
  const results = card.people[0]?.results ?? {};
  const mine = card.kpis.filter((k) => results[k.id]);
  if (!mine.length) return <NoKpis title="No KPIs for your role yet" />;
  return (
    <>
      <Figures results={mine.map((k) => results[k.id])} />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {mine.map((k) => (
          <Sheet key={k.id} className="px-5 py-4">
            <Progress kpi={k} r={results[k.id]} fmt={fmt} />
          </Sheet>
        ))}
      </div>
    </>
  );
}

/** One KPI's result: a ring, where it stands, the figure against its target. */
function Progress({ kpi, r, fmt }: { kpi: KpiDef; r: KpiResult; fmt: Format }) {
  const s = STATUS[r.status];
  const marker = r.target && r.expected !== null && r.expected !== r.target ? (100 * r.expected) / r.target : null;
  return (
    <div className="flex items-center gap-4">
      <ProgressRing
        pct={r.attainment}
        pace={kpi.better === "higher" ? marker : null}
        tone={TONE[r.status]}
        label={`${kpi.name}: ${kpiValue(kpi.unit, r.actual, fmt)}${r.target !== null ? ` of ${kpiValue(kpi.unit, r.target, fmt)}` : ""}, ${s.label.toLowerCase()}`}
      />
      <div className="min-w-0">
        <p className="text-meta text-ink-3">{kpi.name}</p>
        <p className={`text-meta font-semibold ${s.text}`}>{s.label}</p>
        <p className="text-figure leading-tight text-ink">{kpiValue(kpi.unit, r.actual, fmt)}</p>
        <p className="text-meta text-ink-3">
          {r.target !== null ? `of ${kpiValue(kpi.unit, r.target, fmt)}` : "No target set"}
          {marker !== null && <> · {kpiValue(kpi.unit, r.expected, fmt)} by today</>}
          {kpi.better === "lower" && " · lower is better"}
        </p>
      </div>
    </div>
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

/** One KPI for the whole group: its total as a ring, and how many people are where. */
function Overview({ kpi, total, results, fmt }: { kpi: KpiDef; total: KpiResult | undefined; results: KpiResult[]; fmt: Format }) {
  const t = tally(results);
  const s = total ? STATUS[total.status] : STATUS.none;
  const pace = total?.target && total.expected !== null && total.expected !== total.target && kpi.better === "higher" ? (100 * total.expected) / total.target : null;
  return (
    <Sheet className="px-5 py-4">
      <SectionTitle>{kpi.name}</SectionTitle>
      <div className="mt-2 flex items-center gap-4">
        <ProgressRing
          pct={total?.target ? total.attainment : null}
          pace={pace}
          tone={total?.target ? TONE[total.status] : "none"}
          label={`${kpi.name}, everyone: ${kpiValue(kpi.unit, total?.actual, fmt)}${total?.target ? ` of ${kpiValue(kpi.unit, total.target, fmt)}` : ""}`}
        />
        <div className="min-w-0">
          {total?.target ? <p className={`text-meta font-semibold ${s.text}`}>{s.label}</p> : null}
          <p className="text-figure leading-tight text-ink">{kpiValue(kpi.unit, total?.actual, fmt)}</p>
          <p className="text-meta text-ink-3">{total?.target ? `of ${kpiValue(kpi.unit, total.target, fmt)}` : "No targets set"}</p>
          <p className="mt-1 text-meta text-ink-3">
            {t.green} on target · {t.red} behind
          </p>
        </div>
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
      <SectionTitle>Progress by person</SectionTitle>
      <p className="mb-3 text-meta text-ink-3">
        {several ? "The average of each person's KPIs with a target, " : `${card.kpis[0]?.name ?? "The KPI"} `}against 100% of target. The dark tick: where they should be by today.
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
              <span className="relative h-2.5 rounded-full bg-bench" role="img" aria-label={`${p.person.name}: ${pct}% of target${worst ? `, ${STATUS[worst].label.toLowerCase()}` : ""}`}>
                <span className="block h-full rounded-full" style={{ width: `${Math.min(100, pct)}%`, background: worst ? STATUS_COLOR[worst] : STATUS_COLOR.none }} />
                {pace !== null && pace < 100 && <span className="absolute -top-1 h-4.5 w-0.5 rounded bg-ink" style={{ left: `calc(${pace}% - 1px)` }} aria-hidden />}
              </span>
            )}
            <span className="text-right font-semibold text-ink tabular-nums" title={several && count ? `Average of ${fmt.plural(count, "KPI")}` : undefined}>
              {pct === null ? "—" : `${pct}%`}
            </span>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}

function Team({ card, fmt, show, href }: { card: KpiScorecard; fmt: Format; show: "people" | "teams"; href: (show: string) => string }) {
  if (!card.people.length) return <NoKpis title="No KPIs for anyone in reach yet" />;
  const all = card.people.flatMap((p) => card.kpis.map((k) => p.results[k.id]).filter((r): r is KpiResult => !!r));
  const t = tally(all);
  const head = (
    <tr className="border-b border-rule text-left text-meta text-ink-3">
      <th className="px-5 py-2 font-medium">{show === "teams" ? "Team" : "Person"}</th>
      {card.kpis.map((k) => (
        <th key={k.id} className="px-3 py-2 text-right font-medium" title={k.description ?? undefined}>
          {k.name}
        </th>
      ))}
    </tr>
  );
  return (
    <>
      <Figures results={all} />

      <div className="mb-5 grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <ByPerson card={card} fmt={fmt} />
        <div className="grid content-start gap-3 md:grid-cols-2">
          {card.kpis.map((k) => (
            <Overview key={k.id} kpi={k} total={card.totals[k.id]} results={card.people.map((p) => p.results[k.id]).filter((r): r is KpiResult => !!r)} fmt={fmt} />
          ))}
          {card.kpis.length % 2 === 1 && (
            <Sheet className="px-5 py-4">
              <SectionTitle>Where everyone stands</SectionTitle>
              <div className="mt-2">
                <Donut
                  title="Results by status"
                  totalLabel="Results"
                  slices={[
                    { label: "On target", value: t.green, color: STATUS_COLOR.green },
                    { label: "Slightly behind", value: t.amber, color: STATUS_COLOR.amber },
                    { label: "Behind", value: t.red, color: STATUS_COLOR.red },
                    { label: "Without a target", value: t.none, color: STATUS_COLOR.none },
                  ]}
                />
              </div>
            </Sheet>
          )}
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
          <thead>{head}</thead>
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
