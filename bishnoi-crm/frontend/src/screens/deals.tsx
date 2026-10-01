import { Download, Plus, Target } from "lucide-react";
import Link from "next/link";
import { LinkButton, buttonClass } from "@/src/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { DealBoard, DealForecast, DealList, DealRow, DealStage, ForecastFigures, SalesFigures, SalesResults } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { Filters, Pager } from "../components/crm/list-controls";
import { TargetProgress } from "../components/deals/target-progress";
import { CATEGORY_LABELS, StageTag, closeLabel, periodsFrom } from "../components/deals/words";
import { shiftMonth } from "../components/field/words";

export const metadata = { title: "Deals" };

// The pipeline three ways:
// - Board: open deals in a column per stage, with each column's value;
// - List: every deal, open or closed, filtered;
// - Forecast: what each person expects to close in a month or quarter, by category;
// - Results: what was won in a month or quarter, against the revenue targets.
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
  const view = (["list", "forecast", "results"] as const).find((v) => v === one(params.view)) ?? "board";
  const teamWide = me.role?.scope !== "own";
  const who = teamWide && one(params.who) !== "me" ? "team" : "me";
  const href = (v: string, w = who) => {
    const q = new URLSearchParams({ ...(v !== "board" && { view: v }), ...(w === "me" && teamWide && { who: w }) });
    return `/deals${q.size ? `?${q}` : ""}`;
  };
  const owner = who === "me" ? "me" : "";
  const month = /^\d{4}-\d{2}$/.test(one(params.period)) ? one(params.period) : periods.thisMonth;

  return (
    <>
      <PageHeader
        title="Deals"
        actions={
          <>
            {view === "results" && can(me, "goals.manage") && (
              <LinkButton href={`/deals/targets?month=${month}`} icon={<Target className="size-4" aria-hidden />}>
                Set targets
              </LinkButton>
            )}
            {can(me, "deals.create") && (
              <LinkButton href="/deals/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
                New deal
              </LinkButton>
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
            { value: "board", label: "Pipeline", href: href("board") },
            { value: "list", label: "All deals", href: href("list") },
            { value: "forecast", label: "Forecast", href: href("forecast") },
            { value: "results", label: "Results", href: href("results") },
          ]}
        />
        {teamWide && (
          <ToggleLinks
            current={who}
            options={[
              { value: "me", label: "Mine", href: href(view, "me") },
              { value: "team", label: me.role?.scope === "all" ? "Everyone" : "My team", href: href(view, "team") },
            ]}
          />
        )}
      </div>

      {view === "board" && <Board fmt={fmt} today={today} owner={owner} period={one(params.period)} periods={periods} mayAdd={can(me, "deals.create")} />}
      {view === "list" && <List fmt={fmt} today={today} owner={owner} params={params} base={href("list")} />}
      {view === "results" && (
        <Results
          fmt={fmt}
          today={today}
          period={one(params.period) || periods.thisMonth}
          periods={periods}
          team={who === "team" && can(me, "reports.view")}
          mayTarget={can(me, "goals.manage")}
        />
      )}
      {view === "forecast" && <Forecast fmt={fmt} period={one(params.period) || periods.thisMonth} periods={periods} showPeople={who === "team"} />}
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
            actions={mayAdd && <LinkButton href="/deals/new" icon={<Plus className="size-4" aria-hidden />}>New deal</LinkButton>}
          >
            Add a deal from a customer&apos;s page, or here, to see it move through the pipeline.
          </Empty>
        </Sheet>
      ) : (
        <div className="-mx-4 overflow-x-auto px-4 pb-2">
          <div className="grid auto-cols-[minmax(15rem,1fr)] grid-flow-col gap-3">
            {board.columns.map((col) => (
              <section key={col.stage.code} aria-label={col.stage.name} className="min-w-0 rounded-[4px] bg-bench/60 p-2">
                <header className="mb-2 px-1">
                  <h2 className="flex items-baseline justify-between gap-2 text-sm font-semibold text-ink">
                    {col.stage.name}
                    <span className="text-meta font-normal text-ink-3">{col.stage.probability}%</span>
                  </h2>
                  <p className="text-meta text-ink-3">
                    {fmt.plural(col.count, "deal")} · {fmt.pesoCompact(col.valueCentavos)}
                  </p>
                </header>
                <ul className="space-y-2">
                  {col.deals.map((d) => (
                    <li key={d.id}>
                      <DealCard deal={d} fmt={fmt} today={today} />
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function DealCard({ deal, fmt, today }: { deal: DealRow; fmt: Format; today: string }) {
  const overdue = deal.state === "open" && deal.expectedCloseOn < today;
  return (
    <Link href={`/deals/${deal.id}`} className="block rounded-[3px] border border-rule bg-sheet px-3 py-2.5 hover:border-hema">
      <p className="truncate text-sm font-medium text-ink">{deal.name}</p>
      <p className="truncate text-meta text-ink-3">{deal.company.name}</p>
      <p className="mt-1.5 flex items-baseline justify-between gap-2 text-meta">
        <span className="font-semibold text-ink">{fmt.peso(deal.valueCentavos)}</span>
        <span className={overdue ? "font-semibold text-danger" : "text-ink-3"}>{closeLabel(deal, today, fmt.dateLabel)}</span>
      </p>
      <p className="mt-0.5 text-meta text-ink-3">
        {CATEGORY_LABELS[deal.forecastCategory]}
        {deal.owner ? ` · ${deal.owner.name}` : ""}
      </p>
    </Link>
  );
}

async function List({
  fmt,
  today,
  owner,
  params,
  base,
}: {
  fmt: Format;
  today: string;
  owner: string;
  params: Record<string, string | string[] | undefined>;
  base: string;
}) {
  const page = Math.max(1, Number(one(params.page)) || 1);
  const state = one(params.state);
  const stage = one(params.stage);
  const closing = one(params.closing);
  const search = one(params.q);
  const q = new URLSearchParams({
    limit: String(SIZE),
    offset: String((page - 1) * SIZE),
    ...(owner && { owner }),
    ...(state && { state }),
    ...(stage && { stage }),
    ...(closing && { closing }),
    ...(search && { q: search }),
  });
  const [list, stages] = await Promise.all([load<DealList>(`/deals?${q}`), load<DealStage[]>("/deal-stages")]);
  const kept = new URLSearchParams(
    Object.entries({ state, stage, closing, q: search }).filter(([, v]) => v) as [string, string][],
  );
  return (
    <>
      <Filters
        search="Deal or customer"
        selects={[
          { name: "state", label: "State", options: [{ value: "", label: "Open, won and lost" }, { value: "open", label: "Open" }, { value: "won", label: "Won" }, { value: "lost", label: "Lost" }] },
          { name: "stage", label: "Stage", options: [{ value: "", label: "Every stage" }, ...stages.map((s) => ({ value: s.code, label: s.name }))] },
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
        ]}
      />
      <p className="mb-3 text-meta text-ink-2">
        {fmt.plural(list.total, "deal")} worth {fmt.peso(list.valueCentavos)}
      </p>
      <Sheet className="overflow-x-auto">
        {list.items.length === 0 ? (
          <div className="px-5 py-2">
            <Empty icon="trend" title="No deals match">
              Clear a filter to see more.
            </Empty>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-meta text-ink-3">
                <th className="px-5 py-2 font-medium">Deal</th>
                <th className="px-3 py-2 font-medium">Stage</th>
                <th className="px-3 py-2 text-right font-medium">Value</th>
                <th className="px-3 py-2 font-medium">Close</th>
                <th className="px-3 py-2 font-medium">Forecast</th>
                <th className="px-5 py-2 font-medium">Owner</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {list.items.map((d) => (
                <tr key={d.id}>
                  <td className="px-5 py-2.5">
                    <Link href={`/deals/${d.id}`} className="font-medium text-hema hover:underline">
                      {d.name}
                    </Link>
                    <p className="text-meta text-ink-3">{d.company.name}</p>
                  </td>
                  <td className="px-3 py-2.5">
                    <StageTag deal={d} />
                  </td>
                  <td className="px-3 py-2.5 text-right whitespace-nowrap">{fmt.peso(d.valueCentavos)}</td>
                  <td className={`px-3 py-2.5 whitespace-nowrap ${d.state === "open" && d.expectedCloseOn < today ? "font-semibold text-danger" : "text-ink-2"}`}>
                    {fmt.dateLabel(d.expectedCloseOn)}
                  </td>
                  <td className="px-3 py-2.5 text-ink-2">{d.state === "lost" ? d.lostReason : CATEGORY_LABELS[d.forecastCategory]}</td>
                  <td className="px-5 py-2.5 text-ink-2">{d.owner?.name ?? "No one"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Sheet>
      <Pager total={list.total} page={page} size={SIZE} base={kept.size ? `${base}${base.includes("?") ? "&" : "?"}${kept}` : base} />
    </>
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
              <span className={`size-2.5 rounded-[2px] ${b.style}`} aria-hidden />
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
          <Empty icon="trend" title="Nothing expected to close">
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

async function Results({
  fmt,
  today,
  period,
  periods,
  team,
  mayTarget,
}: {
  fmt: Format;
  today: string;
  period: string;
  periods: ReturnType<typeof periodsFrom>;
  team: boolean;
  mayTarget: boolean;
}) {
  const view = team ? "team" : "mine";
  const r = await load<SalesResults>(`/sales/results?view=${view}&period=${encodeURIComponent(period)}`);
  const t = r.totals;
  const exportLink = (report: string) =>
    r.canExport && (
      <a href={`/deals/export?report=${report}&view=${view}&period=${encodeURIComponent(r.period)}`} download className={buttonClass("default", "sm")}>
        <Download className="size-4" aria-hidden />
        Download CSV
      </a>
    );
  const tiles = [
    { label: "Quoted", value: fmt.peso(t.quotedCentavos), note: fmt.plural(t.quoteCount, "quote") },
    { label: "Deals won", value: String(t.wonCount), note: fmt.peso(t.wonCentavos) },
    { label: "Deals lost", value: String(t.lostCount), note: fmt.peso(t.lostCentavos) },
    { label: "Win rate", value: t.winRate === null ? "None decided" : `${t.winRate}%`, note: "of deals won or lost" },
  ];

  return (
    <>
      <Filters selects={[{ name: "period", label: "Period", options: resultPeriods(periods) }]} />
      <div className="mb-4 grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,2fr)]">
        <Sheet className="px-5 py-4">
          <TargetProgress
            figures={t}
            start={r.start}
            end={r.end}
            today={today}
            fmt={fmt}
            label={`Won in ${r.label}`}
            href={mayTarget && /^\d{4}-\d{2}$/.test(r.period) ? `/deals/targets?month=${r.period}` : undefined}
          />
        </Sheet>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-2">
          {tiles.map((x) => (
            <Sheet key={x.label} className="px-4 py-3">
              <p className="text-meta text-ink-3">{x.label}</p>
              <p className="mt-1 text-figure text-ink">{x.value}</p>
              <p className="text-meta text-ink-3">{x.note}</p>
            </Sheet>
          ))}
        </div>
      </div>

      {team && (
        <Sheet className="mb-4 overflow-x-auto">
          <div className="px-5 pt-4"><SectionTitle action={r.people.length > 0 && exportLink("people")}>By person</SectionTitle></div>
          {r.people.length === 0 ? (
            <div className="px-5 py-2">
              <Empty icon="trend" title="No sellers yet">
                People whose role can create deals or quotes show up here.
              </Empty>
            </div>
          ) : (
            <FiguresTable fmt={fmt} rows={r.people.map((p) => ({ key: p.person.id, name: p.person.name, sub: p.team?.name ?? "No team", f: p }))} />
          )}
          {r.teams.length > 1 && (
            <>
              <div className="border-t border-rule px-5 pt-4"><SectionTitle action={exportLink("teams")}>By team</SectionTitle></div>
              <FiguresTable fmt={fmt} rows={r.teams.map((x) => ({ key: x.team?.id ?? "none", name: x.team?.name ?? "No team", f: x }))} />
            </>
          )}
        </Sheet>
      )}

      <div className="grid gap-3 lg:grid-cols-2">
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
        {r.lostReasons.length > 0 && (
          <Sheet className="px-5 py-4 lg:col-span-2">
            <SectionTitle>Why deals were lost</SectionTitle>
            <Ranked fmt={fmt} empty="" rows={r.lostReasons.map((x) => ({ key: x.reason, name: x.reason, value: x.lostCentavos, note: fmt.plural(x.count, "deal") }))} />
          </Sheet>
        )}
      </div>
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
          <th className="px-3 py-2 text-right font-medium">Of target</th>
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
              <Link href={x.href} className="truncate text-hema hover:underline">
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
