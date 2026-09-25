import { ChevronLeft, ChevronRight, Target, Upload } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import { NoAccess } from "../components/admin/words";
import type { PersonMonth, Performance } from "../components/field/types";
import { MEASURES, progress, shiftMonth } from "../components/field/words";

export const metadata = { title: "Field work" };

/** "3 / 10" and a thin bar under it; the goal-less just the number. */
function Cell({ actual, goal, money, fmt }: { actual: number; goal: number | undefined; money?: boolean; fmt: Format }) {
  const show = (n: number) => (money ? fmt.peso(n) : String(n));
  const pct = progress(actual, goal);
  return (
    <td className="px-3 py-2.5 text-right tabular-nums">
      <span className={pct !== null && pct >= 100 ? "font-semibold text-hema" : ""}>{show(actual)}</span>
      {goal ? <span className="text-ink-3"> / {show(goal)}</span> : null}
      {pct !== null && (
        <div aria-hidden className="mt-1 ml-auto h-1 w-24 overflow-hidden rounded-full bg-rule">
          <div className="h-full rounded-full bg-hema" style={{ width: `${pct}%` }} />
        </div>
      )}
    </td>
  );
}

function Table({ people, month, fmt }: { people: PersonMonth[]; month: string; fmt: Format }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[48rem] text-sm">
        <thead>
          <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
            <th scope="col" className="py-2 pr-3 font-semibold">Person</th>
            {MEASURES.map((m) => (
              <th key={m.key} scope="col" className="px-3 py-2 text-right font-semibold">
                {m.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {people.map((p) => (
            <tr key={p.person.id}>
              <th scope="row" className="py-2.5 pr-3 text-left font-medium">
                <Link href={`/visits?person=${p.person.id}&month=${month}`} className="text-hema hover:underline">
                  {p.person.name}
                </Link>
                <span className="block text-meta font-normal text-ink-3">
                  {p.team?.name ?? "No team"}
                  {!p.goal && " · no goals set"} ·{" "}
                  <Link href={`/field/routes?person=${p.person.id}`} className="text-hema hover:underline">
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
  if (!can(me, "goals.view")) return <NoAccess what="the field work tracker" />;
  const asked = (await searchParams).month;
  const data = await load<Performance>(`/field/performance${typeof asked === "string" ? `?month=${enc(asked)}` : ""}`);
  const fmt = makeFormat(me.org);
  const { month } = data;
  const behind = data.people.filter((p) => p.goal && MEASURES.some((m) => (progress(p.actual[m.key], p.goal![m.key]) ?? 100) < 100));

  return (
    <>
      <PageHeader
        title="Field work"
        actions={
          <>
            {can(me, "goals.import") && (
              <LinkButton href="/field/balances/import" icon={<Upload className="size-4" aria-hidden />}>
                Upload balances
              </LinkButton>
            )}
            {data.canSetGoals && (
              <LinkButton href={`/field/goals?month=${month}`} variant="primary" icon={<Target className="size-4" aria-hidden />}>
                Set goals
              </LinkButton>
            )}
          </>
        }
      >
        Visits and collections against each person&apos;s goals for the month.
      </PageHeader>

      <nav aria-label="Month" className="mb-4 flex items-center gap-2">
        <Link href={`/field?month=${shiftMonth(month, -1)}`} className="rounded-[3px] p-1.5 text-ink-2 hover:bg-bench" aria-label="The month before">
          <ChevronLeft className="size-4" aria-hidden />
        </Link>
        <span className="min-w-36 text-center text-heading">
          {fmt.monthLabel(month)} {month.slice(0, 4)}
        </span>
        {month < data.thisMonth ? (
          <Link href={`/field?month=${shiftMonth(month, 1)}`} className="rounded-[3px] p-1.5 text-ink-2 hover:bg-bench" aria-label="The month after">
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        ) : (
          <span className="w-7" />
        )}
        {month !== data.thisMonth && (
          <Link href="/field" className="ml-2 text-meta text-hema hover:underline">
            This month
          </Link>
        )}
      </nav>

      <Sheet className="mb-5 grid grid-cols-2 gap-px overflow-hidden bg-rule xl:grid-cols-4 [&>*]:bg-sheet">
        {MEASURES.map((m) => (
          <div key={m.key} className="px-5 py-4">
            <span className="block text-figure text-ink">{m.money ? fmt.peso(data.totals[m.key]) : data.totals[m.key]}</span>
            <span className="mt-0.5 block text-meta text-ink-3">{m.label}, everyone</span>
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
                <LinkButton href="/admin/users/new" variant="primary">
                  Add a person
                </LinkButton>
              )
            }
          >
            Give someone the Field agent role (People &amp; access) and they show up here.
          </Empty>
        ) : (
          <Table people={data.people} month={month} fmt={fmt} />
        )}
      </Sheet>
      {behind.length > 0 && month === data.thisMonth && (
        <p className="mt-3 text-meta text-ink-3">
          Still short of a goal this month: {behind.map((p) => p.person.name).join(", ")}.
        </p>
      )}
    </>
  );
}
