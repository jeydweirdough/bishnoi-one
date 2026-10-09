import { redirect } from "next/navigation";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { getCompanyMe } from "@/src/platform/lib/api";
import KpiTargetsPage from "./kpi-targets";
import PerformancePage, { IN_MENU, type Place } from "./performance";

// An administrator's Performance is in Settings: what is measured, the
// month's targets, and everyone's results, a tab each.

const BASE = "/admin/settings/performance";
type Search = Promise<Record<string, string | string[] | undefined>>;

export function PerformanceTabs({ current }: { current: "measures" | "targets" | "results" }) {
  return (
    <div className="mb-4">
      <ToggleLinks
        current={current}
        options={[
          { value: "measures", label: "What is measured", href: BASE },
          { value: "targets", label: "Targets", href: `${BASE}/targets` },
          { value: "results", label: "Results", href: `${BASE}/results` },
        ]}
      />
    </div>
  );
}

const inSettings = (current: "targets" | "results"): Place => ({ results: `${BASE}/results`, targets: `${BASE}/targets`, tabs: <PerformanceTabs current={current} /> });

export function SettingsResults({ searchParams }: { searchParams: Search }) {
  return <PerformancePage searchParams={searchParams} place={inSettings("results")} />;
}

export function SettingsTargets({ searchParams }: { searchParams: Search }) {
  return <KpiTargetsPage searchParams={searchParams} place={inSettings("targets")} />;
}

/** The menu's pages, for everyone but an administrator, whose are in Settings. */
export async function MenuResults({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (me.isOwner) redirect(`${BASE}/results${await query(searchParams)}`);
  return <PerformancePage searchParams={searchParams} place={IN_MENU} />;
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
