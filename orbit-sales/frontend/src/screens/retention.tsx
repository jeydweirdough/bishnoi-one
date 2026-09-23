import { Download } from "lucide-react";
import Link from "next/link";
import { SelectAllBox, SelectBox, SelectableRow, SelectionProvider } from "@/src/platform/bulk/selection";
import { WinBackBulk } from "../components/win-back-bulk";
import { RetentionFigures } from "../components/summary";
import { TrendChart } from "../components/trend-chart";
import { WinBack } from "../components/win-back";
import { NoAccess } from "../components/admin/words";
import { buttonClass } from "@/src/platform/ui/button";
import { Flag } from "@/src/platform/ui/marks";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { rateLabel } from "@/src/platform/lib/labels";
import { orgFormat } from "@/src/platform/lib/org";
import type { ModuleRetention, WatchRow } from "@/src/platform/lib/types";

export const metadata = { title: "Retention" };

function Standing({ row }: { row: WatchRow }) {
  if (row.health === "at_risk") return <Flag letter="!">At risk · no quote in {row.daysSince} days</Flag>;
  return (
    <span className="text-meta font-semibold text-ink-3">
      {row.status === "inactive" ? "Lost · marked inactive" : `Lost · no quote in ${row.daysSince} days`}
    </span>
  );
}

export default async function RetentionPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const search = await searchParams;
  const [me, fmt] = await Promise.all([getCompanyMe(), orgFormat()]);
  if (!can(me, "customers.view")) return <NoAccess what="customers" />;
  const wide = me.role?.scope !== "own";
  // A lead opens on their team; a salesperson has only their own.
  const view = wide && search.view !== "mine" ? "team" : "mine";
  const team = view === "team" && typeof search.team === "string" ? search.team : "";
  const query = `view=${view}${team ? `&team=${enc(team)}` : ""}`;
  const data = await load<ModuleRetention>(`/retention?${query}`);
  const rules = data.rules[0];
  const href = (v: string, t = "") => `/retention?view=${v}${t ? `&team=${t}` : ""}`;
  // Worth a call: the ones with no follow-up yet can be won back several at a time.
  const winnable = data.watch.filter((row) => row.canWinBack && !row.followUp);
  const bulk = winnable.length > 1;
  const teamName = data.teams.find((t) => t.id === team)?.name;
  const whose = view === "mine" ? "your customers" : teamName ?? (me.role?.scope === "team" ? "your team" : "everyone");
  const mayExport = view === "mine" || can(me, "reports.export");

  return (
    <>
      <PageHeader title="Retention">
        A customer is kept when they get a quote. At risk after {rules.atRiskDays} days without one, lost after {rules.lostDays}. Showing {whose}.
      </PageHeader>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        {data.canSeeTeam && (
          <ToggleLinks
            current={view}
            options={[
              { value: "mine", label: "My customers", href: href("mine") },
              { value: "team", label: me.role?.scope === "team" ? "My team" : "Everyone", href: href("team") },
            ]}
          />
        )}
        {view === "team" && data.teams.length > 1 && (
          <ToggleLinks
            current={team}
            options={[{ value: "", label: "Every team", href: href("team") }, ...data.teams.map((t) => ({ value: t.id, label: t.name, href: href("team", t.id) }))]}
          />
        )}
        {mayExport && (
          <a href={`/retention/export?${query}`} download className={buttonClass("default", "sm")}>
            <Download className="size-4" aria-hidden />
            Export CSV
          </a>
        )}
      </div>

      <RetentionFigures summary={data.summary} rules={rules} />

      <div className={view === "team" ? "grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:items-start" : ""}>
        <Sheet className="px-5 pt-4 pb-4">
          <SectionTitle icon="trend">Retention by month</SectionTitle>
          <p className="text-meta text-ink-3">
            Each month compares the {rules.lostDays} days up to its last day with the {rules.lostDays} days before.
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
              Customers with no quote in {rules.atRiskDays} days show up here.
            </Empty>
          ) : (
            <>
              {bulk && (
                <div className="mt-2 border-b border-rule">
                  <SelectAllBox>
                    <span className="text-meta font-semibold text-ink-2">Select all {winnable.length} without a task</span>
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
                        <Link href={`/companies/${row.customerId}`} className="font-semibold text-hema hover:underline">
                          {row.name}
                        </Link>
                        <p className="text-meta text-ink-3">
                          {[
                            view === "team" ? row.teamName : null,
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
                          Task {fmt.dueLabel(row.followUp.dueOn, data.asOf).toLowerCase()}
                          <span className="block text-ink-3">{row.followUp.title}</span>
                        </span>
                      ) : (
                        row.canWinBack && (
                          <WinBack customerId={row.customerId} name={row.name} days={row.daysSince} ownerId={row.owner.id} ownerName={row.owner.name} org={me.org} />
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
