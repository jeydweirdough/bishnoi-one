import { Avatar } from "@/src/platform/ui/avatar";
import { Banner } from "@/src/platform/ui/alert";
import { Amount } from "@/src/platform/ui/amount";
import { buttonClass } from "@/src/platform/ui/button";
import { FigureCard, Pill, type Tone } from "@/src/platform/ui/figures";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { Person } from "@/src/platform/lib/types";
import { shiftMonth } from "@/src/modules/crm/components/field/words";

export const metadata = { title: "Scorecards" };

// Each division's 100-point scorecard from its sales playbook (decided
// 2026-10-22; app/scorecards.py scores it): one card at a time, its people
// best first with the points each KPI gave them, the month's total, a cap a
// missed gate put on it, and the band with its yearly raise. Below, who has
// sold nothing this month. Sales come from Finance's invoices (sent or paid),
// by the salesperson on each.

type Band = { min: number; label: string; raise: string; pip: boolean };
type CardItem = { kpi: string; points: number; on: string; scope?: string; label?: string; group?: string };
type Row = {
  kpi: string;
  name: string;
  unit?: "count" | "money" | "percent";
  on?: string;
  scope?: string;
  actual: number | null;
  target: number | null;
  x: number | null;
  points: number;
  of: number;
  missing: string | null;
};
type Scored = {
  person: { id: string; name: string };
  team: { id: string; name: string } | null;
  role: string;
  items: Row[];
  total: number;
  outOf: number;
  percent: number | null;
  cap: { total: number; why: string } | null;
  band: Band | null;
};
type Scorecards = {
  month: string;
  thisMonth: string;
  financeLinked: boolean;
  cards: { code: string; name: string; description: string | null; people: number }[];
  card: { code: string; name: string; description: string | null; items: CardItem[]; bands: Band[] } | null;
  people: Scored[];
  noSales: Person[] | null;
};

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

function bandTone(b: Band | null): Tone {
  if (!b) return "plain";
  if (b.pip) return "bad";
  return b.min >= 85 ? "good" : b.min >= 75 ? "plain" : "warn";
}

/** A KPI's result as people read it: an amount, a rate, days or a count. */
function shown(r: Row, fmt: Format) {
  if (r.actual === null) return <span className="text-ink-3">{r.missing ?? "No result yet."}</span>;
  const value = r.unit === "money" ? <Amount text={fmt.peso(r.actual)} /> : r.unit === "percent" || r.scope === "team_average" ? `${r.actual}%` : r.actual.toLocaleString("en");
  return (
    <>
      {value}
      {r.on === "attainment" && r.x !== null && <span className="text-ink-3"> · {r.x}% of target</span>}
      {r.missing && <span className="text-ink-3"> · {r.missing}</span>}
    </>
  );
}

export default async function ScorecardsPage({ searchParams, base = "/crm/performance/scorecards", tabs }: { searchParams: Search; base?: string; tabs?: React.ReactNode }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const params = await searchParams;
  const month = /^\d{4}-\d{2}$/.test(one(params.month)) ? one(params.month) : fmt.todayKey().slice(0, 7);
  const data = await load<Scorecards>(`/scorecards?month=${month}${one(params.card) ? `&card=${enc(one(params.card))}` : ""}`);
  const href = (m: string, card = data.card?.code) => `${base}?month=${m}${card ? `&card=${card}` : ""}`;
  const name = `${fmt.monthLabel(data.month)} ${data.month.slice(0, 4)}`;
  const people = data.people;
  const scored = people.filter((p) => p.percent !== null);
  const average = scored.length ? Math.round(scored.reduce((n, p) => n + (p.percent ?? 0), 0) / scored.length) : null;
  const below = people.filter((p) => p.band?.pip).length;

  return (
    <>
      <PageHeader title="Scorecards">
        {name}: each division&apos;s playbook scorecard, out of 100.{data.month === data.thisMonth ? " The month is still running, so targets aren't met yet; the playbooks score the month on the 1st." : ""}
      </PageHeader>
      {tabs}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {data.cards.length > 1 && <ToggleLinks current={data.card?.code ?? ""} options={data.cards.map((c) => ({ value: c.code, label: `${c.name} · ${c.people}`, href: href(data.month, c.code) }))} />}
        <span className="ml-auto flex gap-1">
          <a href={href(shiftMonth(data.month, -1))} className={buttonClass("quiet", "sm")}>
            ‹ {fmt.monthLabel(shiftMonth(data.month, -1))}
          </a>
          {data.month !== data.thisMonth && (
            <a href={href(data.thisMonth)} className={buttonClass("quiet", "sm")}>
              This month
            </a>
          )}
          {data.month < data.thisMonth && (
            <a href={href(shiftMonth(data.month, 1))} className={buttonClass("quiet", "sm")}>
              {fmt.monthLabel(shiftMonth(data.month, 1))} ›
            </a>
          )}
        </span>
      </div>

      {!data.financeLinked && (
        <Banner tone="warn" className="mb-4">
          Finance isn&apos;t linked, so the sales KPIs (IST, NZSD, CRR, NBD, DSO, OCR) have no results. Sales are counted from Finance&apos;s invoices.
        </Banner>
      )}

      {!data.card ? (
        <Sheet className="px-5 py-2">
          <Empty icon="goals" art="gauge" title="No scorecards yet">
            Scorecards come from the sales playbooks. An administrator loads them with the seed tool (app.tools.seed_scorecards).
          </Empty>
        </Sheet>
      ) : (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <FigureCard first figure={{ value: String(people.length), label: "People on this card", note: data.card.name }} />
            <FigureCard figure={{ value: average === null ? "—" : `${average}`, label: "Average score", note: average === null ? "Nobody scored yet" : "Out of 100", ring: average }} />
            <FigureCard figure={{ value: String(below), label: "Below 60", note: below ? "A PIP follows if it repeats next month" : "Nobody", alert: below > 0 }} />
            <FigureCard
              figure={{
                value: data.noSales === null ? "—" : String(data.noSales.length),
                label: "No sales yet",
                note: data.noSales === null ? "Needs Finance" : "This month, no invoice in their name",
                alert: (data.noSales?.length ?? 0) > 0,
              }}
            />
          </div>

          <Sheet className="mb-4 px-5 py-4">
            <SectionTitle icon="goals">{data.card.name}</SectionTitle>
            {data.card.description && <p className="mt-1 text-meta text-ink-3">{data.card.description}</p>}
            <ul className="mt-3 flex flex-wrap gap-1.5">
              {data.card.items.map((i, n) => (
                <li key={`${i.kpi}-${n}`} className="rounded-md bg-bench px-2.5 py-1 text-meta text-ink-2">
                  <span className="font-semibold text-ink">{i.points}</span> {i.label ?? i.kpi.toUpperCase()}
                  {i.group && <span className="text-ink-3"> · {i.group}</span>}
                </li>
              ))}
            </ul>
          </Sheet>

          <Sheet className="mb-4 overflow-x-auto">
            {people.length === 0 ? (
              <div className="px-5 py-2">
                <Empty icon="goals" title="Nobody on this card">
                  People are on a card through their team and role.
                </Empty>
              </div>
            ) : (
              <table className="w-full min-w-[48rem] text-sm">
                <thead>
                  <tr className="border-b border-rule text-left text-meta text-ink-3">
                    <th className="px-4 py-2.5 font-medium">Person</th>
                    {people[0].items.map((r, n) => (
                      <th key={`${r.kpi}-${n}`} className="px-3 py-2.5 font-medium">
                        {r.name}
                        <span className="block font-normal">of {r.of}</span>
                      </th>
                    ))}
                    <th className="px-3 py-2.5 text-right font-medium">Score</th>
                    <th className="px-4 py-2.5 font-medium">Band</th>
                  </tr>
                </thead>
                <tbody>
                  {people.map((p) => (
                    <tr key={p.person.id} className="border-b border-rule align-top last:border-0">
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-2.5">
                          <Avatar name={p.person.name} id={p.person.id} size="sm" />
                          <span className="min-w-0">
                            <span className="block font-medium text-ink">{p.person.name}</span>
                            <span className="block text-meta text-ink-3">{[p.role, p.team?.name].filter(Boolean).join(" · ")}</span>
                          </span>
                        </span>
                      </td>
                      {p.items.map((r, n) => (
                        <td key={`${r.kpi}-${n}`} className="px-3 py-3">
                          <span className={`block font-semibold ${r.points === 0 ? "text-ink-3" : "text-ink"}`}>{r.points}</span>
                          <span className="block text-meta">{shown(r, fmt)}</span>
                        </td>
                      ))}
                      <td className="px-3 py-3 text-right">
                        <span className="block text-base font-semibold text-ink">{p.total}</span>
                        <span className="block text-meta text-ink-3">
                          {p.outOf !== 100 ? `of ${p.outOf} · ${p.percent ?? "—"}%` : "of 100"}
                        </span>
                        {p.cap && <span className="mt-0.5 block text-meta text-danger">Capped at {p.cap.total}: {p.cap.why}</span>}
                      </td>
                      <td className="px-4 py-3">
                        {p.band ? (
                          <>
                            <Pill tone={bandTone(p.band)}>{p.band.label}</Pill>
                            <span className="mt-1 block text-meta text-ink-3">{p.band.pip ? "PIP if it repeats" : `${p.band.raise} raise, on the year's average`}</span>
                          </>
                        ) : (
                          <span className="text-meta text-ink-3">Not scored yet</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Sheet>

          <Sheet className="px-5 py-4">
            <SectionTitle icon="goals">No sales yet this month</SectionTitle>
            {data.noSales === null ? (
              <p className="mt-2 text-meta text-ink-3">Shown once Finance is linked: sales are its invoices.</p>
            ) : data.noSales.length === 0 ? (
              <p className="mt-2 text-meta text-ink-3">Everyone on a scorecard has at least one invoice this month.</p>
            ) : (
              <ul className="mt-3 flex flex-wrap gap-2">
                {data.noSales.map((p) => (
                  <li key={p.id} className="flex items-center gap-2 rounded-lg border border-rule px-2.5 py-1.5 text-sm text-ink">
                    <Avatar name={p.name ?? ""} id={p.id} size="sm" />
                    {p.name}
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
        </>
      )}
    </>
  );
}
