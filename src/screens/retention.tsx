import { Download } from "lucide-react";
import Link from "next/link";
import { SelectAllBox, SelectBox, SelectableRow, SelectionProvider } from "@/src/platform/bulk/selection";
import { WinBackBulk } from "../components/win-back-bulk";
import { RetentionFigures } from "../components/summary";
import { TrendChart } from "../components/trend-chart";
import { WinBack } from "../components/win-back";
import { buttonClass } from "@/src/platform/ui/button";
import { Flag } from "@/src/platform/ui/marks";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { ByDivision } from "../components/by-division";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { rateLabel } from "@/src/platform/lib/labels";
import { salesWorkspace, teamsFor } from "@/src/platform/lib/module";
import { orgFormat } from "@/src/platform/lib/org";
import type { ModuleRetention, RetentionByDivision, WatchRow } from "@/src/platform/lib/types";

export const metadata = { title: "Retention" };

/** With several divisions in one list there is no single window, so the
 *  headline figures use the widest: the one that counts a customer lost last. */
function longest(windows: { atRiskDays: number; lostDays: number; divisionName?: string }[]) {
  return windows.reduce((a, b) => (b.lostDays > a.lostDays ? b : a), windows[0] ?? { atRiskDays: 0, lostDays: 0 });
}

function Standing({ row }: { row: WatchRow }) {
  if (row.health === "at_risk") return <Flag letter="!">At risk · no quote in {row.daysSince} days</Flag>;
  return (
    <span className="text-meta font-semibold text-ink-3">
      {row.status === "inactive" ? "Lost · marked inactive" : `Lost · no quote in ${row.daysSince} days`}
    </span>
  );
}

export default async function RetentionPage({ searchParams }: { params: Promise<Record<string, never>>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const search = await searchParams;
  const [ws, me, fmt] = await Promise.all([salesWorkspace(), getCompanyMe(), orgFormat()]);
  const reportTeams = teamsFor(ws, "report");
  // Comparing divisions only means something with Reports in more than one.
  const canCompare = new Set(reportTeams.map((t) => t.division)).size > 1;
  const asked = search.view;
  const view = asked === "team" && reportTeams.length ? "team" : asked === "divisions" && canCompare ? "divisions" : "mine";
  const href = (v: string, t = "") => `/retention?view=${v}${t ? `&team=${t}` : ""}`;

  // Division against division: the same question, grouped differently. It was
  // its own page once; it is a view of this one now.
  if (view === "divisions") {
    const data = await load<RetentionByDivision>("/retention/divisions");
    return (
      <>
        <PageHeader title="Retention">
          A customer is kept when they get a quote. Each division is measured over its own window: the days after which it
          counts a quiet customer as lost.
        </PageHeader>
        <div className="mb-3">
          <ToggleLinks
            current="divisions"
            options={[
              { value: "mine", label: "My customers", href: href("mine") },
              { value: "team", label: "All my teams", href: href("team") },
              { value: "divisions", label: "By division", href: href("divisions") },
            ]}
          />
        </div>
        <ByDivision data={data} org={me.org} />
      </>
    );
  }

  const team = typeof search.team === "string" && reportTeams.some((t) => t.code === search.team) ? search.team : "";
  const teamDivision = team ? (reportTeams.find((t) => t.code === team)?.division ?? "") : "";
  const query = `view=${view}${view === "team" && team ? `&team=${enc(team)}&division=${enc(teamDivision)}` : ""}`;
  const data = await load<ModuleRetention>(`/retention?${query}`);
  // One window per division. With one it reads as it always did; with more,
  // each is named, because a merged list has to group rather than average.
  const windows = data.rules;
  const widest = windows.length === 1 ? windows[0] : longest(windows);
  // Worth a call: the ones with no follow-up yet can be won back several at a time.
  const winnable = data.watch.filter((row) => row.canWinBack && !row.followUp);
  const bulk = winnable.length > 1;
  const whose = view === "mine" ? "your customers" : team ? `${reportTeams.find((t) => t.code === team)?.name}` : "the whole team";

  return (
    <>
      <PageHeader title="Retention">
        A customer is kept when they get a quote.{" "}
        {windows.length === 1 ? (
          <>
            At risk after {windows[0].atRiskDays} days without one, lost after {windows[0].lostDays}.
          </>
        ) : (
          <>
            Each division counts its own way:{" "}
            {windows.map((w) => `${w.divisionName} at risk after ${w.atRiskDays}, lost after ${w.lostDays}`).join("; ")}.
          </>
        )}{" "}
        Showing {whose}.
      </PageHeader>

      {/* One filter row, above everything it scopes. */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {data.canSeeTeam && (
          <ToggleLinks
            current={view}
            options={[
              { value: "mine", label: "My customers", href: href("mine") },
              { value: "team", label: reportTeams.length > 1 ? "All my teams" : "Whole team", href: href("team") },
              ...(canCompare ? [{ value: "divisions", label: "By division", href: href("divisions") }] : []),
            ]}
          />
        )}
        {view === "team" && reportTeams.length > 1 && (
          <ToggleLinks
            current={team}
            options={[
              { value: "", label: "Every team", href: href("team") },
              ...reportTeams.map((t) => ({
                value: t.code,
                label: ws.manyDivisions ? `${t.divisionName} · ${t.name}` : t.name,
                href: href("team", t.code),
              })),
            ]}
          />
        )}
        {/* Beside the filters it exports, not across the page from them. */}
        <a href={`/retention/export?${query}`} download className={buttonClass("default", "sm")}>
          <Download className="size-4" aria-hidden />
          Export CSV
        </a>
      </div>

      <RetentionFigures summary={data.summary} rules={widest} />

      {/* Side by side only when there's a per-rep table to sit beside the chart. */}
      <div className={view === "team" ? "grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:items-start" : ""}>
        <Sheet className="px-5 pt-4 pb-4">
          <SectionTitle icon="trend">Retention by month</SectionTitle>
          <p className="text-meta text-ink-3">
            Each month compares the {widest.lostDays} days up to its last day with the {widest.lostDays} days before.
          </p>
          <TrendChart points={data.trend} title={`Retention by month, ${whose}`} org={me.org} />
        </Sheet>

        {view === "team" && (
          <Sheet className="px-5 pt-4 pb-3">
            <SectionTitle icon="reps">By rep</SectionTitle>
            {data.reps.length === 0 ? (
              <p className="py-3 text-meta text-ink-3">No customers here yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[30rem] text-left text-sm">
                  <thead>
                    <tr className="border-b border-rule text-caps text-ink-3 uppercase">
                      <th scope="col" className="py-2 pr-3 font-semibold">Owner</th>
                      <th scope="col" className="px-2 py-2 text-right font-semibold">Customers</th>
                      <th scope="col" className="px-2 py-2 text-right font-semibold">At risk</th>
                      <th scope="col" className="px-2 py-2 text-right font-semibold">Kept</th>
                      <th scope="col" className="py-2 pl-2 text-right font-semibold">Retention</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-rule tabular-nums">
                    {data.reps.map((r) => (
                      <tr key={r.id ?? "nobody"}>
                        <th scope="row" className="py-2 pr-3 text-left font-medium">
                          {r.name ?? <span className="text-ink-3">No owner</span>}
                        </th>
                        <td className="px-2 py-2 text-right">{r.customers}</td>
                        <td className="px-2 py-2 text-right">{r.atRisk}</td>
                        <td className="px-2 py-2 text-right text-ink-2">{r.base ? `${r.retained} of ${r.base}` : "—"}</td>
                        <td className="py-2 pl-2 text-right font-semibold">{rateLabel(r.rate)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Sheet>
        )}
      </div>

      <SelectionProvider key={query} items={bulk ? winnable.map((row) => ({ id: row.customerId, name: row.name })) : []}>
        <Sheet className="mt-5 px-5 pt-4 pb-2">
          <SectionTitle icon="worthACall">Worth a call</SectionTitle>
          <p className="text-meta text-ink-3">At risk first, the ones closest to lost at the top; then those lost lately, while they&apos;re still winnable.</p>
          {data.watch.length === 0 ? (
            <Empty icon="retention" title="Nobody slipping away">
              Customers with no quote in {widest.atRiskDays} days show up here.
            </Empty>
          ) : (
            <>
              {bulk && (
                <div className="mt-2 border-b border-rule">
                  <SelectAllBox>
                    <span className="text-meta font-semibold text-ink-2">Select all {winnable.length} without a follow-up</span>
                  </SelectAllBox>
                </div>
              )}
              <ul className="mt-1 divide-y divide-rule">
                {data.watch.map((row) => (
                  <SelectableRow key={row.customerId} id={row.customerId} as="li" className="-mx-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 px-5 py-3">
                    <div className="flex min-w-0 items-start gap-3">
                      {bulk && (
                        <span className="w-4 shrink-0 pt-0.5">
                          {row.canWinBack && !row.followUp && <SelectBox id={row.customerId} label={row.name} />}
                        </span>
                      )}
                      <div className="min-w-0">
                        <Link href={`/customers/${row.customerId}`} className="font-semibold text-hema hover:underline">
                          {row.name}
                        </Link>
                        <p className="text-meta text-ink-3">
                          {[
                            ws.manyDivisions ? row.divisionName : null,
                            ws.teams.length > 1 ? row.teamName : null,
                            view === "team" ? (row.owner.name ?? "No owner") : null,
                            row.lastQuoteOn && `last quote ${fmt.dateLabel(row.lastQuoteOn)}`,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                        <Standing row={row} />
                      </div>
                    </div>
                    <div className="text-right text-meta">
                      {row.followUp ? (
                        <span className="text-ink-2">
                          Follow-up {fmt.dueLabel(row.followUp.dueOn, data.asOf).toLowerCase()}
                          <span className="block text-ink-3">{row.followUp.title}</span>
                        </span>
                      ) : (
                        row.canWinBack && (
                          <WinBack
                            customerId={row.customerId}
                            name={row.name}
                            days={row.daysSince}
                            ownerId={row.owner.id}
                            ownerName={row.owner.name}
                            org={me.org}
                          />
                        )
                      )}
                    </div>
                  </SelectableRow>
                ))}
              </ul>
            </>
          )}
        </Sheet>
        {bulk && <WinBackBulk org={me.org} />}
      </SelectionProvider>
    </>
  );
}
