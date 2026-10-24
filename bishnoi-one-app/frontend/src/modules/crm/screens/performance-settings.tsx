import { redirect } from "next/navigation";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { getCompanyMe } from "@/src/platform/lib/api";
import KpiTargetsPage from "@/src/modules/crm/screens/kpi-targets";
import PerformancePage, { IN_MENU, type Place } from "@/src/modules/crm/screens/performance";
import ScorecardsPage from "@/src/modules/crm/screens/scorecards";

// An administrator's Performance is in Settings: what is measured, the
// month's targets, and everyone's results, a tab each.

const BASE = "/crm/admin/settings/performance";
type Search = Promise<Record<string, string | string[] | undefined>>;

export function PerformanceTabs({ current }: { current: "measures" | "targets" | "results" | "scorecards" }) {
  return (
    <div className="mb-4">
      <ToggleLinks
        current={current}
        options={[
          { value: "measures", label: "Measures", href: BASE },
          { value: "targets", label: "Targets", href: `${BASE}/targets` },
          { value: "results", label: "Results", href: `${BASE}/results` },
          { value: "scorecards", label: "Scorecards", href: `${BASE}/scorecards` },
        ]}
      />
    </div>
  );
}

const inSettings = (current: "targets" | "results"): Place => ({ results: `${BASE}/results`, targets: `${BASE}/targets`, tabs: <PerformanceTabs current={current} /> });

export function SettingsResults({ searchParams }: { searchParams: Search }) {
  return <PerformancePage searchParams={searchParams} place={inSettings("results")} />;
}

export function SettingsScorecards({ searchParams }: { searchParams: Search }) {
  return <ScorecardsPage searchParams={searchParams} base={`${BASE}/scorecards`} tabs={<PerformanceTabs current="scorecards" />} />;
}

export function SettingsTargets({ searchParams }: { searchParams: Search }) {
  return <KpiTargetsPage searchParams={searchParams} place={inSettings("targets")} />;
}

/** The old Performance page: an administrator's results are in Settings; everyone
 *  else's are on their profile now (a lead's team on its "My team" tab). Kept as an
 *  address so the links to it, and anyone's bookmark, still land in the right place. */
export async function MenuResults({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (me.isOwner) redirect(`${BASE}/results${await query(searchParams)}`);
  const params = await searchParams;
  const month = typeof params.month === "string" && /^\d{4}-\d{2}$/.test(params.month) ? params.month : null;
  const team = me.role?.scope !== "own" && params.who !== "me";
  const q = new URLSearchParams({ ...(team && { tab: "team" }), ...(month && { month }), ...(team && typeof params.role === "string" && { role: params.role }), ...(team && params.show === "teams" && { show: "teams" }) });
  redirect(`/crm/account${q.size ? `?${q}` : ""}`);
}

export async function MenuTargets({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (me.isOwner) redirect(`${BASE}/targets${await query(searchParams)}`);
  return <KpiTargetsPage searchParams={searchParams} place={IN_MENU} />;
}

/** The page's search, to carry over to where it moved. */
export async function query(searchParams: Search): Promise<string> {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(await searchParams)) if (typeof v === "string") q.set(k, v);
  const s = q.toString();
  return s ? `?${s}` : "";
}
