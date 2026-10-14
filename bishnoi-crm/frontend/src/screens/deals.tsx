import { ArrowDown, ArrowUp, Download, Target } from "lucide-react";
import Link from "next/link";
import { LinkButton, buttonClass } from "@/src/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { Board as KanbanBoard, type BoardCard } from "@/src/platform/ui/board";
import { moveDealStage } from "../actions/deals";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import { Avatar } from "@/src/platform/ui/avatar";
import type { DealBoard, DealForecast, DealList, DealRow, DealStage, DealSummary, ForecastFigures, SalesFigures, SalesResults } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { Filters, Pager } from "../components/crm/list-controls";
import { NewDealButton } from "../components/deals/new-deal";
import { PeriodPicker } from "../components/deals/period-picker";
import { TargetProgress } from "../components/deals/target-progress";
import { Donut, RAMP, SERIES } from "../components/deals/donut";
import { Breakdown, FigureCard, type Figure } from "../components/deals/figure-card";
import { CATEGORY_LABELS, PRIORITIES, PriorityFlag, StageTag, closeLabel, periodsFrom } from "../components/deals/words";
import { shiftMonth } from "../components/field/words";

export const metadata = { title: "Deals" };

// Deals, as a sales team reads them:
// - Open deals, the first thing seen, laid out as the dashboard is: four
//   figures (won in the period, the weighted pipeline, quoted, win rate), then
//   revenue against target and the pipeline by stage and priority, then the
//   open deals as a table or a board, then who sold and what. The period
//   (?results=, this month unless picked) sits beside the tabs. So a team with
//   sales but nothing open never sees an empty page;
// - Closed deals: the same figures and charts, and the table;
// - Forecast: what each person expects to close in a month or quarter, by category.
// Old addresses: ?view=results is the first tab, its ?period= the results period.
const SIZE = 50;

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function DealsPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "deals.view")) return <NoAccess what="deals" />;
  const params = await searchParams;
  const fmt = makeFormat(me.org);
  const today = fmt.todayKey();
  const periods = periodsFrom(today);
  // Old addresses: ?view=board is open deals on the board; ?view=list, the table.
  const asked = one(params.view);
  const view = (["closed", "forecast"] as const).find((v) => v === asked) ?? "open";
  const layout = view === "open" && (asked === "board" || one(params.layout) === "board") ? "board" : "table";
  const teamWide = me.role?.scope !== "own";
  const who = teamWide && one(params.who) !== "me" ? "team" : "me";
  const results = one(params.results) || (asked === "results" ? one(params.period) : "");
  const href = (v: string, w = who, l = layout) => {
    const q = new URLSearchParams({
      ...(v !== "open" && { view: v }),
      ...(v === "open" && l === "board" && { layout: l }),
      ...(v === "open" && results && { results }),
      ...(w === "me" && teamWide && { who: w }),
    });
    return `/deals${q.size ? `?${q}` : ""}`;
  };
  const owner = who === "me" ? "me" : "";
  const month = /^\d{4}-\d{2}$/.test(results) ? results : periods.thisMonth;

  return (
    <>
      <PageHeader
        title="Deals"
        actions={
          <>
            {view === "open" && can(me, "goals.manage") && (
              <LinkButton href={`/performance/targets?month=${month}`} icon={<Target className="size-4" aria-hidden />}>
                Set targets
              </LinkButton>
            )}
            {can(me, "deals.create") && (
              <NewDealButton />
            )}
          </>
        }
      >
        Business expected from customers: how much, by when, and how likely.
      </PageHeader>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <ToggleLinks
          current={view}
          options={[
            { value: "open", label: "Open deals", href: href("open") },
            { value: "closed", label: "Closed", href: href("closed") },
            { value: "forecast", label: "Forecast", href: href("forecast") },
          ]}
        />
        {view === "open" && <PeriodPicker bare name="results" value={results || periods.thisMonth} presets={resultPeriods(periods)} />}
        {teamWide && (
          <span className="ml-auto">
            <ToggleLinks
              current={who}
              options={[
                { value: "me", label: "Mine", href: href(view, "me") },
                { value: "team", label: me.role?.scope === "all" ? "Everyone" : me.role?.scope === "managed" ? "My teams" : "My team", href: href(view, "team") },
              ]}
            />
          </span>
        )}
      </div>

      {view === "open" && (
        <Overview
          fmt={fmt}
          today={today}
          period={results || periods.thisMonth}
          owner={owner}
          team={who === "team" && can(me, "reports.view")}
          mayTarget={can(me, "goals.manage")}
          filtered={Boolean(one(params.q) || one(params.stage) || one(params.priority) || one(params.closing) || (asked !== "results" && one(params.period)))}
        >
          <div className="mb-3">
            <ToggleLinks
              current={layout}
              options={[
                { value: "table", label: "Table", href: href("open", who, "table") },
                { value: "board", label: "Board", href: href("open", who, "board") },
              ]}
            />
          </div>
          {layout === "board" ? (
            <Board fmt={fmt} today={today} owner={owner} period={asked === "results" ? "" : one(params.period)} periods={periods} mayAdd={can(me, "deals.create")} />
          ) : (
            <Table fmt={fmt} today={today} owner={owner} state="open" params={params} base={href("open")} mayAdd={can(me, "deals.create")} />
          )}
        </Overview>
      )}
      {view === "closed" && (
        <>
          <Summary state="closed" owner={owner} fmt={fmt} mayAdd={false} filtered={Boolean(one(params.q) || one(params.stage) || one(params.priority))}>
            <Table fmt={fmt} today={today} owner={owner} state="closed" params={params} base={href("closed")} mayAdd={false} />
          </Summary>
        </>
      )}
      {view === "forecast" && <Forecast fmt={fmt} period={one(params.period) || periods.thisMonth} periods={periods} showPeople={who === "team"} />}
    </>
  );
}

/**
 * The four cards above the deals: the figures, then the deals by probability,
 * stage and priority; then the deals (children). With none at all, and no
 * filter set, just that and the next step.
 */
async function Summary({
  state,
  owner,
  fmt,
  mayAdd,
  filtered,
  children,
}: {
  state: "open" | "closed";
  owner: string;
  fmt: Format;
  mayAdd: boolean;
  filtered: boolean;
  children: React.ReactNode;
}) {
  const s = await load<DealSummary>(`/deals-summary?state=${state}${owner ? `&owner=${owner}` : ""}`);
  if (s.count === 0 && !filtered)
    return (
      <Sheet className="px-5 py-2">
        <Empty icon="trend" title={state === "open" ? "No open deals" : "No closed deals yet"} actions={mayAdd && <NewDealButton variant="default" />}>
          {state === "open" ? "Add one from a customer's page, or here, to see the pipeline and what's likely to close." : "Deals won or lost show up here."}
        </Empty>
      </Sheet>
    );
  const pct = (part: number, whole: number) => (whole ? Math.round((100 * part) / whole) : null);
  const shown = (n: number | null) => (n === null ? "—" : `${n}%`);
  const closed = s.wonCount + s.lostCount;
  const likelyShare = pct(s.weightedCentavos, s.valueCentavos);
  const winRate = pct(s.wonCount, closed);
  // The figure first, large; what it is under it; then how it compares (a rate, a share).
  const figures: Figure[] =
    state === "open"
      ? [
          { value: fmt.peso(s.valueCentavos), label: "Pipeline value", note: fmt.plural(s.count, "open deal") },
          { value: shown(likelyShare), label: "Likely to close", note: `${fmt.peso(s.weightedCentavos)} weighted by probability`, ring: likelyShare },
          {
            value: fmt.peso(s.thisMonthCentavos),
            label: "Expected this month",
            note: pct(s.thisMonthCentavos, s.weightedCentavos) === null ? "Nothing weighted yet" : `${pct(s.thisMonthCentavos, s.weightedCentavos)}% of the weighted pipeline`,
          },
          { value: s.count ? fmt.peso(Math.round(s.valueCentavos / s.count)) : "—", label: "Average deal", note: "Value per open deal" },
        ]
      : [
          { value: shown(winRate), label: "Win rate", note: `${s.wonCount} won of ${closed} closed`, ring: winRate },
          { value: fmt.peso(s.wonCentavos), label: "Won", note: fmt.plural(s.wonCount, "deal") },
          { value: String(s.lostCount), label: "Deals lost", note: closed ? `${pct(s.lostCount, closed)}% of those closed` : "None closed yet" },
          { value: s.wonCount ? fmt.peso(Math.round(s.wonCentavos / s.wonCount)) : "—", label: "Average won deal", note: "Value per deal won" },
        ];
  const stageColor = (i: number) => SERIES[i % SERIES.length];
  const priorities = s.byPriority.map((b) => {
    const p = PRIORITIES.find((x) => x.value === b.priority)!;
    return { label: p.label, value: b.count, color: p.color };
  });
  const urgent = s.byPriority.filter((b) => b.priority === "urgent" || b.priority === "high").reduce((t, b) => t + b.count, 0);
  const likely = s.byProbability[0]?.count ?? 0;
  const top = [...s.byStage].sort((a, b) => b.count - a.count)[0];
  const none = s.count === 0 ? (state === "open" ? "No open deals yet" : "No closed deals yet") : undefined;
  return (
    <>
      <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {figures.map((f, n) => (
          <FigureCard key={f.label} figure={f} first={n === 0} />
        ))}
      </div>
      <div className={`mb-5 grid gap-3 ${state === "open" ? "lg:grid-cols-3" : "lg:grid-cols-2"}`}>
        {state === "open" && (
          <Breakdown value={shown(pct(likely, s.count))} label="of open deals are 80% likely or more" title="By probability" empty={none} art="gauge">
            <Donut title="Open deals by probability" slices={s.byProbability.map((b, i) => ({ label: b.label, value: b.count, color: RAMP[i] }))} />
          </Breakdown>
        )}
        <Breakdown value={top && s.count ? shown(pct(top.count, s.count)) : "—"} label={top && s.count ? `are at ${top.name}, the busiest stage` : "No deals in a stage yet"} title="By stage" empty={none} art="steps">
          {s.byStage.length ? (
            <Donut title="Deals by stage" slices={s.byStage.map((st, i) => ({ label: st.name, value: st.count, color: stageColor(i), note: fmt.peso(st.valueCentavos) }))} />
          ) : (
            <p className="py-6 text-meta text-ink-3">No deals here yet.</p>
          )}
        </Breakdown>
        <Breakdown value={shown(pct(urgent, s.count))} label="are urgent or high priority" title="By priority" empty={none} art="flag">
          <Donut title="Deals by priority" slices={priorities} />
        </Breakdown>
      </div>
      {children}
    </>
  );
}

function periodOptions(periods: ReturnType<typeof periodsFrom>, any: string | null) {
  return [
    ...(any !== null ? [{ value: "", label: any }] : []),
    { value: periods.thisMonth, label: "This month" },
    { value: periods.nextMonth, label: "Next month" },
    { value: periods.thisQuarter, label: "This quarter" },
  ];
}

async function Board({
  fmt,
  today,
  owner,
  period,
  periods,
  mayAdd,
}: {
  fmt: Format;
  today: string;
  owner: string;
  period: string;
  periods: ReturnType<typeof periodsFrom>;
  mayAdd: boolean;
}) {
  const q = new URLSearchParams({ ...(owner && { owner }), ...(period && { period }) });
  const board = await load<DealBoard>(`/deals-board${q.size ? `?${q}` : ""}`);
  const total = board.columns.reduce((s, c) => s + c.valueCentavos, 0);
  const weighted = board.columns.reduce((s, c) => s + c.weightedCentavos, 0);
  const count = board.columns.reduce((s, c) => s + c.count, 0);
  return (
    <>
      <Filters selects={[{ name: "period", label: "Closing", options: periodOptions(periods, "Any time") }]} />
      <p className="mb-3 text-meta text-ink-2">
        {fmt.plural(count, "open deal")} worth {fmt.peso(total)}; {fmt.peso(weighted)} weighted by probability.
      </p>
      {count === 0 ? (
        <Sheet className="px-5 py-2">
          <Empty
            icon="trend"
            title="No open deals"
            actions={mayAdd && <NewDealButton variant="default" />}
          >
            Add a deal from a customer&apos;s page, or here, to see it move through the pipeline.
          </Empty>
        </Sheet>
      ) : (
        <KanbanBoard
          columns={board.columns.map((col) => ({ key: col.stage.code, label: col.stage.name, aside: `${col.stage.probability}%`, note: `${fmt.plural(col.count, "deal")} · ${fmt.pesoCompact(col.valueCentavos)}`, hint: "No deals at this stage" }))}
          cards={board.columns.flatMap((col) => col.deals.map((d) => dealCard(d, fmt, today)))}
          // Any open stage to any other; won and lost are decided on the deal's page, with the quote or the reason.
          moves={[{ from: "*", to: "*", step: "{to}", label: "Move to {to}" }]}
          run={moveDealStage}
        />
      )}
    </>
  );
}

/** A deal as a board card: its name and priority, the customer, the value and when it closes, then its forecast and owner. */
function dealCard(deal: DealRow, fmt: Format, today: string): BoardCard {
  return {
    id: deal.id,
    column: deal.stage.code,
    href: `/deals/${deal.id}`,
    title: deal.name,
    flag: deal.priority ? <PriorityFlag priority={deal.priority} /> : undefined,
    sub: deal.company.name,
    value: fmt.peso(deal.valueCentavos),
    when: closeLabel(deal, today, fmt.dateLabel),
    late: deal.state === "open" && deal.expectedCloseOn < today,
    meta: `${CATEGORY_LABELS[deal.forecastCategory]}${deal.owner ? ` · ${deal.owner.name}` : ""}`,
    movable: deal.can.edit,
  };
}

const SORTS = ["name", "created", "value", "stage", "priority", "close"] as const;
type SortKey = (typeof SORTS)[number];

/** The deals as a table: a column for each thing a sales team asks about, each sortable. */
async function Table({
  fmt,
  today,
  owner,
  state,
  params,
  base,
  mayAdd,
}: {
  fmt: Format;
  today: string;
  owner: string;
  state: "open" | "closed";
  params: Record<string, string | string[] | undefined>;
  base: string;
  mayAdd: boolean;
}) {
  const page = Math.max(1, Number(one(params.page)) || 1);
  const stage = one(params.stage);
  const priority = one(params.priority);
  const closing = one(params.closing);
  const search = one(params.q);
  const sort = SORTS.find((x) => x === one(params.sort));
  const desc = one(params.desc) === "1";
  const q = new URLSearchParams({
    state,
    limit: String(SIZE),
    offset: String((page - 1) * SIZE),
    ...(owner && { owner }),
    ...(stage && { stage }),
    ...(priority && { priority }),
    ...(closing && { closing }),
    ...(search && { q: search }),
    ...(sort && { sort, desc: String(desc) }),
  });
  const [list, stages] = await Promise.all([load<DealList>(`/deals?${q}`), load<DealStage[]>("/deal-stages")]);
  const kept = (extra: Record<string, string>) => {
    const k = new URLSearchParams(Object.entries({ stage, priority, closing, q: search, ...(sort && { sort }), ...(desc && { desc: "1" }), ...extra }).filter(([, v]) => v) as [string, string][]);
    return k.size ? `${base}${base.includes("?") ? "&" : "?"}${k}` : base;
  };
  const sortHref = (key: SortKey) => kept({ sort: key, desc: sort === key && !desc ? "1" : "" });
  const Head = ({ k, children, right }: { k: SortKey; children: React.ReactNode; right?: boolean }) => (
    <th className={`px-3 py-2 font-medium ${right ? "text-right" : ""}`} aria-sort={sort === k ? (desc ? "descending" : "ascending") : undefined}>
      <Link href={sortHref(k)} className="inline-flex items-center gap-1 hover:text-ink">
        {children}
        {sort === k && (desc ? <ArrowDown className="size-3" aria-hidden /> : <ArrowUp className="size-3" aria-hidden />)}
      </Link>
    </th>
  );
  const shownStages = stages.filter((s) => (state === "open" ? s.outcome === "open" : s.outcome !== "open"));

  return (
    <>
      <Filters
        search="Deal or customer"
        selects={[
          { name: "stage", label: "Stage", options: [{ value: "", label: "All stages" }, ...shownStages.map((s) => ({ value: s.code, label: s.name }))] },
          { name: "priority", label: "Priority", options: [{ value: "", label: "Any priority" }, ...PRIORITIES.map((p) => ({ value: p.value ?? "none", label: p.label }))] },
          ...(state === "open"
            ? [
                {
                  name: "closing",
                  label: "Closing",
                  options: [
                    { value: "", label: "Any time" },
                    { value: "overdue", label: "Overdue" },
                    { value: "this_month", label: "This month" },
                    { value: "next_month", label: "Next month" },
                    { value: "this_quarter", label: "This quarter" },
                  ],
                },
              ]
            : []),
        ]}
      />
      <Sheet className="overflow-x-auto">
        <p className="border-b border-rule px-5 py-2.5 text-meta text-ink-2">
          {fmt.plural(list.total, "deal")} worth {fmt.peso(list.valueCentavos)}
        </p>
        {list.items.length === 0 ? (
          <div className="px-5 py-2">
            <Empty
              icon="trend"
              title={stage || priority || closing || search ? "No deals match" : state === "open" ? "No open deals" : "No closed deals yet"}
              actions={state === "open" && mayAdd && <NewDealButton variant="default" />}
            >
              {stage || priority || closing || search ? "Clear a filter to see more." : "Deals added on a customer's page, or here, show up in this table."}
            </Empty>
          </div>
        ) : (
          <table className="w-full min-w-[60rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-meta text-ink-3">
                <th className="px-5 py-2 font-medium">
                  <Link href={sortHref("name")} className="inline-flex items-center gap-1 hover:text-ink">
                    Deal
                    {sort === "name" && (desc ? <ArrowDown className="size-3" aria-hidden /> : <ArrowUp className="size-3" aria-hidden />)}
                  </Link>
                </th>
                <th className="px-3 py-2 font-medium">Created by</th>
                <Head k="created">Created</Head>
                <Head k="value" right>
                  Value
                </Head>
                <th className="px-3 py-2 font-medium">Assigned to</th>
                <Head k="stage">Stage</Head>
                <Head k="priority">Priority</Head>
                {state === "open" && <th className="px-3 py-2 font-medium">Next step</th>}
                <Head k="close">{state === "open" ? "Close date" : "Closed"}</Head>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {list.items.map((d) => (
                <tr key={d.id} className="hover:bg-bench/40">
                  <td className="px-5 py-2.5">
                    <Link href={`/deals/${d.id}`} className="font-medium text-ink hover:underline">
                      {d.name}
                    </Link>
                    <p className="text-meta text-ink-3">{d.company.name}</p>
                  </td>
                  <td className="px-3 py-2.5">
                    <Person who={d.createdBy} />
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap text-ink-2">{fmt.dateLabel(d.createdAt.slice(0, 10))}</td>
                  <td className="px-3 py-2.5 text-right whitespace-nowrap tabular-nums">{fmt.peso(d.valueCentavos)}</td>
                  <td className="px-3 py-2.5">
                    <Person who={d.owner} />
                  </td>
                  <td className="px-3 py-2.5">
                    <StageTag deal={d} />
                  </td>
                  <td className="px-3 py-2.5">
                    <PriorityFlag priority={d.priority} />
                  </td>
                  {state === "open" && (
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      {d.nextStep ? (
                        <span className={d.nextStep.at.slice(0, 10) < today ? "font-semibold text-danger" : "text-ink-2"} title={d.nextStep.subject}>
                          {fmt.dateLabel(d.nextStep.at.slice(0, 10))}
                          <span className="block max-w-40 truncate text-meta text-ink-3">{d.nextStep.subject}</span>
                        </span>
                      ) : (
                        <span className="text-meta text-ink-3">None planned</span>
                      )}
                    </td>
                  )}
                  <td className={`px-3 py-2.5 whitespace-nowrap ${d.state === "open" && d.expectedCloseOn < today ? "font-semibold text-danger" : "text-ink-2"}`}>
                    {fmt.dateLabel(d.expectedCloseOn)}
                    {d.state === "lost" && d.lostReason && <span className="block text-meta font-normal text-ink-3">{d.lostReason}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Sheet>
      <Pager total={list.total} page={page} size={SIZE} base={kept({})} />
    </>
  );
}

function Person({ who }: { who: { id: string; name: string } | null }) {
  if (!who) return <span className="text-meta text-ink-3">Unassigned</span>;
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap text-ink-2">
      <Avatar name={who.name} id={who.id} size="sm" />
      {who.name}
    </span>
  );
}

const FORECAST_BARS: { key: keyof ForecastFigures; label: string; style: string }[] = [
  { key: "wonCentavos", label: "Won", style: "bg-filed" },
  { key: "commitCentavos", label: "Commit", style: "bg-hema" },
  { key: "bestCaseCentavos", label: "Best case", style: "bg-due-later/60" },
  { key: "pipelineCentavos", label: "Pipeline", style: "bg-rule-strong" },
];

async function Forecast({ fmt, period, periods, showPeople }: { fmt: Format; period: string; periods: ReturnType<typeof periodsFrom>; showPeople: boolean }) {
  const forecast = await load<DealForecast>(`/deals-forecast?period=${encodeURIComponent(period)}`);
  const rows = showPeople ? forecast.people : [];
  const widest = Math.max(1, ...[forecast.totals, ...rows].map((r) => FORECAST_BARS.reduce((s, b) => s + (r[b.key] as number), 0)));
  const t = forecast.totals;
  return (
    <>
      <Filters selects={[{ name: "period", label: "Period", options: periodOptions(periods, null) }]} />
      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        {FORECAST_BARS.map((b) => (
          <Sheet key={b.key} className="px-4 py-3">
            <p className="flex items-center gap-2 text-meta text-ink-3">
              <span className={`size-2.5 rounded-full ${b.style}`} aria-hidden />
              {b.label}
            </p>
            <p className="mt-1 text-figure text-ink">{fmt.peso(t[b.key] as number)}</p>
          </Sheet>
        ))}
      </div>
      <Sheet className="px-5 py-4">
        <h2 className="text-sm font-semibold text-ink">{forecast.label}</h2>
        <p className="mb-4 text-meta text-ink-3">
          Won is what closed in the period; the rest is open deals expected to close in it. Weighted by probability: {fmt.peso(t.weightedCentavos)}. Omitted and lost deals
          are left out.
        </p>
        {t.deals === 0 ? (
          <Empty icon="trend" title="No deals expected to close">
            Deals with an expected close date in {forecast.label} show up here.
          </Empty>
        ) : (
          <ul className="space-y-3">
            {[...rows.map((r) => ({ name: r.owner?.name ?? "No one", r })), ...(rows.length > 1 || !rows.length ? [{ name: "Total", r: t }] : [])].map(({ name, r }) => (
              <li key={name} className="grid items-center gap-x-4 gap-y-1 sm:grid-cols-[10rem_minmax(0,1fr)_9rem]">
                <span className={`text-sm ${name === "Total" ? "font-semibold text-ink" : "text-ink-2"}`}>{name}</span>
                <div className="flex h-3 overflow-hidden rounded-full bg-bench" role="img" aria-label={FORECAST_BARS.map((b) => `${b.label} ${fmt.peso(r[b.key] as number)}`).join(", ")}>
                  {FORECAST_BARS.map((b) => (
                    <span key={b.key} className={b.style} style={{ width: `${(100 * (r[b.key] as number)) / widest}%` }} />
                  ))}
                </div>
                <span className="text-meta text-ink-2 sm:text-right">
                  {fmt.peso(r.wonCentavos + r.commitCentavos)} won or committed
                </span>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}

function resultPeriods(periods: ReturnType<typeof periodsFrom>) {
  const [y, q] = periods.thisQuarter.split("-Q").map(Number);
  return [
    { value: periods.thisMonth, label: "This month" },
    { value: shiftMonth(periods.thisMonth, -1), label: "Last month" },
    { value: periods.thisQuarter, label: "This quarter" },
    { value: q === 1 ? `${y - 1}-Q4` : `${y}-Q${q - 1}`, label: "Last quarter" },
  ];
}

/**
 * The open tab, as the dashboard reads: the four figures; revenue against
 * target beside the pipeline by stage and priority; the deals (children);
 * then who sold and what. With nothing open, one card says so in place of
 * the charts, and the table is left out.
 */
async function Overview({
  fmt,
  today,
  period,
  owner,
  team,
  mayTarget,
  filtered,
  children,
}: {
  fmt: Format;
  today: string;
  period: string;
  owner: string;
  team: boolean;
  mayTarget: boolean;
  filtered: boolean;
  /** The open deals: the table or the board. */
  children: React.ReactNode;
}) {
  const view = team ? "team" : "mine";
  const [r, s] = await Promise.all([
    load<SalesResults>(`/sales/results?view=${view}&period=${encodeURIComponent(period)}`),
    load<DealSummary>(`/deals-summary?state=open${owner ? `&owner=${owner}` : ""}`),
  ]);
  const t = r.totals;
  const pct = (part: number, whole: number) => (whole ? Math.round((100 * part) / whole) : null);
  const decided = t.wonCount + t.lostCount;
  const targets = mayTarget && /^\d{4}-\d{2}$/.test(r.period) ? `/performance/targets?month=${r.period}` : undefined;
  const figures: Figure[] = [
    {
      value: fmt.peso(t.wonCentavos),
      label: `Won in ${r.label}`,
      note: t.targetCentavos ? `${t.attainment ?? 0}% of the ${fmt.peso(t.targetCentavos)} target` : `${fmt.plural(t.wonCount, "deal")}, no target set`,
      ring: t.targetCentavos ? t.attainment : null,
      href: "/deals?view=closed",
    },
    {
      value: fmt.peso(s.weightedCentavos),
      label: "Pipeline, weighted",
      note: s.count ? `${fmt.peso(s.valueCentavos)} in ${fmt.plural(s.count, "open deal")}` : "No open deals",
      ring: pct(s.weightedCentavos, s.valueCentavos),
    },
    { value: fmt.peso(t.quotedCentavos), label: `Quoted in ${r.label}`, note: fmt.plural(t.quoteCount, "quote"), href: "/quotes" },
    {
      value: t.winRate === null ? "—" : `${t.winRate}%`,
      label: "Win rate",
      note: decided ? `${fmt.plural(t.wonCount, "deal")} won, ${t.lostCount} lost` : "No deals decided yet",
      ring: t.winRate,
      href: "/deals?view=closed",
    },
  ];
  const busiest = [...s.byStage].sort((a, b) => b.count - a.count)[0];
  const urgent = s.byPriority.filter((b) => b.priority === "urgent" || b.priority === "high").reduce((n, b) => n + b.count, 0);
  const exportLink = (report: string) =>
    r.canExport && (
      <a href={`/deals/export?report=${report}&view=${view}&period=${encodeURIComponent(r.period)}`} download className={buttonClass("default", "sm")}>
        <Download className="size-4" aria-hidden />
        Download CSV
      </a>
    );
  const sold = r.customers.length > 0 || r.products.length > 0;

  return (
    <>
      <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {figures.map((f, n) => (
          <FigureCard key={f.label} figure={f} first={n === 0} />
        ))}
      </div>

      <div className="mb-5 grid gap-3 lg:grid-cols-3">
        <Sheet className="px-5 py-4">
          <p className="text-caps text-ink-3 uppercase">Revenue against target</p>
          <div className="mt-2">
            <TargetProgress figures={t} start={r.start} end={r.end} today={today} fmt={fmt} label={`Won in ${r.label}`} href={targets} withWinRate={false} />
          </div>
        </Sheet>
        {s.count === 0 ? (
          <div className="lg:col-span-2">
            <Breakdown title="Pipeline" value="" label="" empty="No open deals" emptyNote="Add one from a customer's page, or with New deal, to see the pipeline by stage and priority." art="steps">
              {null}
            </Breakdown>
          </div>
        ) : (
          <>
            <Breakdown value={`${pct(busiest.count, s.count)}%`} label={`are at ${busiest.name}, the busiest stage`} title="Pipeline by stage" art="steps">
              <Donut title="Open deals by stage" totalLabel="Deals" slices={s.byStage.map((st, i) => ({ label: st.name, value: st.count, color: SERIES[i % SERIES.length], note: fmt.peso(st.valueCentavos) }))} />
            </Breakdown>
            <Breakdown value={`${pct(urgent, s.count)}%`} label="are urgent or high priority" title="Pipeline by priority" art="flag">
              <Donut
                title="Open deals by priority"
                totalLabel="Deals"
                slices={s.byPriority.map((b) => {
                  const p = PRIORITIES.find((x) => x.value === b.priority)!;
                  return { label: p.label, value: b.count, color: p.color };
                })}
              />
            </Breakdown>
          </>
        )}
      </div>

      {(s.count > 0 || filtered) && <div className="mb-5">{children}</div>}

      {team && r.people.length > 0 && (
        <Sheet className="mb-3 overflow-x-auto">
          <div className="px-5 pt-4">
            <SectionTitle action={exportLink("people")}>By person, {r.label}</SectionTitle>
          </div>
          <FiguresTable fmt={fmt} rows={r.people.map((p) => ({ key: p.person.id, name: p.person.name, sub: p.team?.name ?? "No team", f: p }))} />
          {r.teams.length > 1 && (
            <>
              <div className="border-t border-rule px-5 pt-4">
                <SectionTitle action={exportLink("teams")}>By team</SectionTitle>
              </div>
              <FiguresTable fmt={fmt} rows={r.teams.map((x) => ({ key: x.team?.id ?? "none", name: x.team?.name ?? "No team", f: x }))} />
            </>
          )}
        </Sheet>
      )}

      {(sold || r.lostReasons.length > 0) && (
        <div className="grid gap-3 lg:grid-cols-2">
          {sold && (
            <>
              <Sheet className="px-5 py-4">
                <SectionTitle action={r.customers.length > 0 && exportLink("customers")}>Top customers</SectionTitle>
                <Ranked
                  fmt={fmt}
                  empty="No deals won in this period."
                  rows={r.customers.map((c) => ({ key: c.customer.id, name: c.customer.name, href: `/companies/${c.customer.id}`, value: c.wonCentavos, note: fmt.plural(c.wonCount, "deal") }))}
                />
              </Sheet>
              <Sheet className="px-5 py-4">
                <SectionTitle action={r.products.length > 0 && exportLink("products")}>Top products</SectionTitle>
                <Ranked
                  fmt={fmt}
                  empty="No deals won in this period."
                  rows={r.products.map((p) => ({ key: p.product.id ?? p.product.name, name: p.product.name, value: p.wonCentavos, note: p.quantity ? fmt.plural(p.quantity, "unit") : "" }))}
                />
              </Sheet>
            </>
          )}
          {r.lostReasons.length > 0 && (
            <Sheet className="px-5 py-4 lg:col-span-2">
              <SectionTitle>Loss reasons</SectionTitle>
              <Ranked fmt={fmt} empty="" rows={r.lostReasons.map((x) => ({ key: x.reason, name: x.reason, value: x.lostCentavos, note: fmt.plural(x.count, "deal") }))} />
            </Sheet>
          )}
        </div>
      )}
    </>
  );
}

function FiguresTable({ fmt, rows }: { fmt: Format; rows: { key: string; name: string; sub?: string; f: SalesFigures }[] }) {
  return (
    <table className="mt-2 w-full text-sm">
      <thead>
        <tr className="border-b border-rule text-left text-meta text-ink-3">
          <th className="px-5 py-2 font-medium">Name</th>
          <th className="px-3 py-2 text-right font-medium">Target</th>
          <th className="px-3 py-2 text-right font-medium">Won</th>
          <th className="px-3 py-2 text-right font-medium">Attainment</th>
          <th className="px-3 py-2 text-right font-medium">Win rate</th>
          <th className="px-5 py-2 text-right font-medium">Quoted</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-rule">
        {rows.map(({ key, name, sub, f }) => (
          <tr key={key}>
            <td className="px-5 py-2.5">
              <span className="font-medium text-ink">{name}</span>
              {sub && <p className="text-meta text-ink-3">{sub}</p>}
            </td>
            <td className="px-3 py-2.5 text-right whitespace-nowrap text-ink-2">{f.targetCentavos ? fmt.peso(f.targetCentavos) : "None"}</td>
            <td className="px-3 py-2.5 text-right whitespace-nowrap">
              {fmt.peso(f.wonCentavos)}
              <p className="text-meta text-ink-3">{fmt.plural(f.wonCount, "deal")}</p>
            </td>
            <td className={`px-3 py-2.5 text-right whitespace-nowrap ${f.attainment === null ? "text-ink-3" : f.attainment >= 100 ? "font-semibold text-filed" : "text-ink-2"}`}>
              {f.attainment === null ? "No target" : `${f.attainment}%`}
            </td>
            <td className="px-3 py-2.5 text-right whitespace-nowrap text-ink-2">{f.winRate === null ? "None decided" : `${f.winRate}%`}</td>
            <td className="px-5 py-2.5 text-right whitespace-nowrap text-ink-2">
              {fmt.peso(f.quotedCentavos)}
              <p className="text-meta text-ink-3">{fmt.plural(f.quoteCount, "quote")}</p>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** A short list ranked by value, each with a bar against the largest. */
function Ranked({ fmt, rows, empty }: { fmt: Format; rows: { key: string; name: string; href?: string; value: number; note: string }[]; empty: string }) {
  if (rows.length === 0) return <p className="py-4 text-meta text-ink-3">{empty}</p>;
  const top = Math.max(1, ...rows.map((x) => x.value));
  return (
    <ul className="mt-2 space-y-2.5">
      {rows.map((x) => (
        <li key={x.key}>
          <p className="flex items-baseline justify-between gap-3 text-sm">
            {x.href ? (
              <Link href={x.href} className="truncate text-ink hover:underline">
                {x.name}
              </Link>
            ) : (
              <span className="truncate text-ink">{x.name}</span>
            )}
            <span className="shrink-0 whitespace-nowrap text-ink">
              {fmt.peso(x.value)}
              {x.note && <span className="text-meta text-ink-3"> · {x.note}</span>}
            </span>
          </p>
          <div className="mt-1 h-1.5 rounded-full bg-bench" aria-hidden>
            <span className="block h-full rounded-full bg-hema" style={{ width: `${(100 * x.value) / top}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
