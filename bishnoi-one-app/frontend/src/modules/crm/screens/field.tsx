import { ChevronLeft, ChevronRight, Target, Upload } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import type { DetailingSummary, PersonMonth, Performance } from "@/src/modules/crm/components/field/types";
import { MEASURES, REACTIONS, progress, shiftMonth } from "@/src/modules/crm/components/field/words";
import { counted, termsOf, worded, type Terms } from "@/src/modules/crm/components/terms/terms";

export const metadata = { title: "Field work" };

/** "3 / 10" and a thin bar under it; the goal-less just the number. */
function Cell({ actual, goal, money, fmt }: { actual: number; goal: number | undefined; money?: boolean; fmt: Format }) {
  const show = (n: number) => (money ? fmt.peso(n) : String(n));
  const pct = progress(actual, goal);
  return (
    <td className="px-3 py-2.5 text-right tabular-nums">
      <span className={pct !== null && pct >= 100 ? "font-semibold text-ink" : ""}>{show(actual)}</span>
      {goal ? <span className="text-ink-3"> / {show(goal)}</span> : null}
      {pct !== null && (
        <div aria-hidden className="mt-1 ml-auto h-1 w-24 overflow-hidden rounded-full bg-rule">
          <div className="h-full rounded-full bg-hema" style={{ width: `${pct}%` }} />
        </div>
      )}
    </td>
  );
}

function Table({ people, month, fmt, terms }: { people: PersonMonth[]; month: string; fmt: Format; terms: Terms }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[48rem] text-sm">
        <thead>
          <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
            <th scope="col" className="py-2 pr-3 font-semibold">Person</th>
            {MEASURES.map((m) => (
              <th key={m.key} scope="col" className="px-3 py-2 text-right font-semibold">
                {worded(m.label, terms)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {people.map((p) => (
            <tr key={p.person.id}>
              <th scope="row" className="py-2.5 pr-3 text-left font-medium">
                <Link href={`/crm/visits?person=${p.person.id}&month=${month}`} className="text-ink hover:underline">
                  {p.person.name}
                </Link>
                <span className="block text-meta font-normal text-ink-3">
                  {p.team?.name ?? "No team"}
                  {!p.goal && " · no goals set"} ·{" "}
                  <Link href={`/crm/field/routes?person=${p.person.id}`} className="text-ink hover:underline">
                    Route
                  </Link>
                </span>
              </th>
              {MEASURES.map((m) => (
                <Cell key={m.key} actual={p.actual[m.key]} goal={p.goal?.[m.key]} money={m.money} fmt={fmt} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Each field agent's month against their goals: for their Team Lead (their
 *  team) and the admin (everyone), who also sets the goals. */
export default async function FieldPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  const terms = termsOf(me);
  if (!can(me, "goals.view")) return <NoAccess what="the field work tracker" />;
  const asked = (await searchParams).month;
  const data = await load<Performance>(`/field/performance${typeof asked === "string" ? `?month=${enc(asked)}` : ""}`);
  const fmt = makeFormat(me.org);
  const { month } = data;
  const detailing = can(me, "visits.view") ? await load<DetailingSummary>(`/field/detailing?month=${enc(month)}`) : null;
  const behind = data.people.filter((p) => p.goal && MEASURES.some((m) => (progress(p.actual[m.key], p.goal![m.key]) ?? 100) < 100));

  return (
    <>
      <PageHeader
        title="Field work"
        actions={
          <>
            {can(me, "goals.import") && (
              <LinkButton href="/crm/field/balances/import" icon={<Upload className="size-4" aria-hidden />}>
                Upload balances
              </LinkButton>
            )}
            {data.canSetGoals && (
              <LinkButton href={`/crm/performance/targets?month=${month}`} variant="primary" icon={<Target className="size-4" aria-hidden />}>
                Set targets
              </LinkButton>
            )}
          </>
        }
      >
        Visits and collections against each person&apos;s goals for the month.
      </PageHeader>

      <nav aria-label="Month" className="mb-4 flex items-center gap-2">
        <Link href={`/crm/field?month=${shiftMonth(month, -1)}`} className="rounded-md p-1.5 text-ink-2 hover:bg-bench" aria-label="Previous month">
          <ChevronLeft className="size-4" aria-hidden />
        </Link>
        <span className="min-w-36 text-center text-heading">
          {fmt.monthLabel(month)} {month.slice(0, 4)}
        </span>
        {month < data.thisMonth ? (
          <Link href={`/crm/field?month=${shiftMonth(month, 1)}`} className="rounded-md p-1.5 text-ink-2 hover:bg-bench" aria-label="Next month">
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        ) : (
          <span className="w-7" />
        )}
        {month !== data.thisMonth && (
          <Link href="/crm/field" className="ml-2 text-meta text-ink hover:underline">
            This month
          </Link>
        )}
      </nav>

      <Sheet className="mb-5 grid grid-cols-2 gap-px overflow-hidden bg-rule xl:grid-cols-4 [&>*]:bg-sheet">
        {MEASURES.map((m) => (
          <div key={m.key} className="px-5 py-4">
            <span className="block text-figure text-ink">{m.money ? fmt.peso(data.totals[m.key]) : data.totals[m.key]}</span>
            <span className="mt-0.5 block text-meta text-ink-3">{worded(m.label, terms)}, team total</span>
          </div>
        ))}
      </Sheet>

      <Sheet className="px-5 pt-2 pb-3">
        {data.people.length === 0 ? (
          <Empty
            title="No field agents here yet"
            icon="people"
            actions={
              can(me, "admin.users") && (
                <LinkButton href="/platform/roles/people" variant="primary">
                  Add a person
                </LinkButton>
              )
            }
          >
            Give someone the Field agent role (People and access) and they show up here.
          </Empty>
        ) : (
          <Table terms={terms} people={data.people} month={month} fmt={fmt} />
        )}
      </Sheet>
      {behind.length > 0 && month === data.thisMonth && (
        <p className="mt-3 text-meta text-ink-3">
          Still short of a goal this month: {behind.map((p) => p.person.name).join(", ")}.
        </p>
      )}
      {detailing && <Detailing summary={detailing} terms={terms} />}
    </>
  );
}

// One colour each, good to bad: green, pale green, brand, grey, amber, red.
const SWATCH: Record<string, string> = {
  will_prescribe: "bg-filed",
  already_prescribes: "bg-filed/45",
  interested: "bg-hema/60",
  neutral: "bg-rule-strong",
  concerns: "bg-due-today",
  not_interested: "bg-danger",
};

/** The month's detailing: each product, on how many visits and doctors, and how doctors took it. */
function Detailing({ summary, terms }: { summary: DetailingSummary; terms: Terms }) {
  return (
    <Sheet className="mt-5 px-5 pt-3 pb-4">
      <SectionTitle icon="visit">{terms.detailing}</SectionTitle>
      <p className="mb-3 text-meta text-ink-3">
        {summary.detailedVisits} of {summary.visits} {summary.visits === 1 ? "visit" : "visits"} this month recorded the products discussed.
      </p>
      {summary.products.length === 0 ? (
        <Empty compact icon="products" title="No products recorded yet">Agents add the products they discussed when they log a visit.</Empty>
      ) : (
        <>
          <ul className="space-y-3">
            {summary.products.map((p) => (
              <li key={p.product.id} className="grid items-center gap-x-4 gap-y-1 sm:grid-cols-[14rem_minmax(0,1fr)]">
                <span className="text-sm">
                  <span className="font-medium text-ink">{p.product.name}</span>
                  <span className="block text-meta text-ink-3">
                    {p.visits} {p.visits === 1 ? "visit" : "visits"} · {counted(p.doctors, terms)}
                  </span>
                </span>
                <div
                  className="flex h-3 overflow-hidden rounded-full bg-bench"
                  role="img"
                  aria-label={REACTIONS.filter((r) => p.reactions[r.value]).map((r) => `${r.label}: ${p.reactions[r.value]}`).join(", ")}
                >
                  {REACTIONS.map((r) => (
                    <span key={r.value} className={SWATCH[r.value]} style={{ width: `${(100 * (p.reactions[r.value] ?? 0)) / p.visits}%` }} />
                  ))}
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-meta text-ink-3">
            {REACTIONS.map((r) => (
              <span key={r.value} className="inline-flex items-center gap-1.5">
                <span className={`size-2.5 rounded-full ${SWATCH[r.value]}`} aria-hidden />
                {r.label}
              </span>
            ))}
          </p>
        </>
      )}
    </Sheet>
  );
}
