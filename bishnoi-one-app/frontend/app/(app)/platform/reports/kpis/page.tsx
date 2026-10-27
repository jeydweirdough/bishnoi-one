import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";
import { apiFor, ApiError } from "@/src/platform/lib/api";
import { myModules } from "@/src/one/mine";
import { moduleCookie } from "@/src/platform/lib/session-cookie";
import { makeFormat } from "@/src/platform/lib/format";
import type { KpiScorecard, KpiResult, KpiDef, Me, Org, TeamRow } from "@/src/platform/lib/types";
import { PageHeader } from "@/src/platform/ui/sheet";
import { ReportTable } from "@/src/platform/reports/table";
import type { Cell, ReportColumn } from "@/src/platform/reports/types";
import { kpiValue, STATUS } from "@/src/modules/crm/components/kpis/words";

export const metadata = { title: "Company KPIs" };
type User = { id: string; fullName: string; isActive: boolean; role: { id: string; name: string; scope: string }; team: { id: string; name: string } | null };
type Search = Promise<Record<string, string | string[] | undefined>>;
const base = "/platform/reports/kpis";
const text = (value: string): Cell => ({ raw: value, text: value });

export default async function CompanyKpis({ searchParams }: { searchParams: Search }) {
  const account = await getAccount();
  if (!account.isCompanyAdmin) redirect("/platform");
  const header = <PageHeader title="Company KPIs" crumbs={[{ href: "/platform/reports", label: "Reports Center" }]}>Results against targets, from company and role summaries through divisions, teams and individual users.</PageHeader>;
  if (!myModules(account).some(m => m.key === "crm")) return <>{header}<p>Per-user KPIs are available when CRM is enabled for your company.</p></>;
  if (!(await cookies()).get(moduleCookie("crm"))?.value) redirect(`/auth/enter/crm?next=${encodeURIComponent(base)}`);
  const params = await searchParams;
  const api = apiFor("crm");
  let first: KpiScorecard;
  let me: Me & { org: Org };
  const month = typeof params.month === "string" && /^\d{4}-(0[1-9]|1[0-2])$/.test(params.month) ? params.month : "";
  try {
    [first, me] = await Promise.all([
      api.get<KpiScorecard>(`/kpi-scorecard?view=team${month ? `&month=${month}` : ""}`),
      api.get<Me & { org: Org }>("/auth/me"),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect(`/auth/enter/crm?next=${encodeURIComponent(base)}`);
    return <>{header}<p role="status">KPI results cannot be loaded with your current access or connection. <Link href={base} className="underline">Try again</Link>.</p></>;
  }
  const fmt = makeFormat(me.org);
  const roleResults = await Promise.allSettled(first.roles.map(r => r.id === first.role ? Promise.resolve(first) : api.get<KpiScorecard>(`/kpi-scorecard?view=team&month=${first.month}&role=${encodeURIComponent(r.id)}`)));
  const [teamsResult, usersResult] = await Promise.allSettled([api.get<TeamRow[]>("/admin/teams"), api.get<User[]>("/admin/users")]);
  const teams = teamsResult.status === "fulfilled" ? teamsResult.value : [];
  const users = usersResult.status === "fulfilled" ? usersResult.value : [];
  const cards = roleResults.flatMap(r => r.status === "fulfilled" ? [r.value] : []);
  const scopeOrder = ["all", "managed", "team", "own"];
  const roleRank = (id: string | null) => {
    const scope = users.find(u => u.role.id === id)?.role.scope;
    const i = scopeOrder.indexOf(scope ?? "");
    return i < 0 ? scopeOrder.length : i;
  };
  cards.sort((a, b) => roleRank(a.role) - roleRank(b.role));
  const rows: Cell[][] = [];
  const add = (level: string, role: string, team: string, person: string, k: KpiDef, result?: KpiResult) => {
    rows.push([text(level), text(role), text(team), text(person), text(k.name), text(kpiValue(k.unit, result?.actual, fmt)), text(kpiValue(k.unit, result?.target, fmt)), { raw: result?.attainment ?? null, text: result?.attainment == null ? "-" : `${result.attainment}%` }, text(result ? STATUS[result.status].label : "Not assigned")]);
  };
  for (const card of cards) {
    const role = first.roles.find(r => r.id === card.role)?.name ?? "Role";
    for (const k of card.kpis) if (card.totals[k.id]) add("Company / role", role, "All teams", "All users in this role", k, card.totals[k.id]);
    const teamIds = [...new Set(card.people.map(p => p.team?.id ?? ""))];
    // The team's API order is division, then its branches. Keep users beneath their team.
    teamIds.sort((a, b) => {
      const ai = teams.findIndex(t => t.id === a), bi = teams.findIndex(t => t.id === b);
      return (ai < 0 ? teams.length : ai) - (bi < 0 ? teams.length : bi);
    });
    for (const id of teamIds) {
      const team = teams.find(t => t.id === id);
      const parent = teams.find(t => t.id === team?.parentId);
      const summary = card.teams.find(t => (t.team?.id ?? "") === id);
      const name = [parent?.name, team?.name ?? summary?.team?.name ?? "No team"].filter(Boolean).join(" / ");
      for (const k of card.kpis) if (summary?.results[k.id]) add(team?.parentId ? "Branch" : "Division / team", role, name, team?.manager ? `Manager: ${team.manager.name}` : "Team total", k, summary.results[k.id]);
      for (const p of card.people.filter(p => (p.team?.id ?? "") === id)) {
        for (const k of card.kpis) if (p.results[k.id]) add("User", role, name, p.person.name, k, p.results[k.id]);
      }
    }
  }
  const measured = new Set(cards.flatMap(c => c.people.map(p => p.person.id)));
  // A failed role request must not turn a measured user's KPI into a misleading unassigned row.
  const failedRoles = new Set(first.roles.filter((_, i) => roleResults[i].status === "rejected").map(r => r.id));
  for (const u of [...users].sort((a, b) => roleRank(a.role.id) - roleRank(b.role.id))) {
    if (measured.has(u.id) || failedRoles.has(u.role.id)) continue;
    rows.push([text("User"), text(u.role.name), text(u.team?.name ?? "No team"), text(u.fullName), text("No active KPI assigned"), text("-"), text("-"), { raw: null, text: "-" }, text(u.isActive ? "Not assigned" : "Inactive")]);
  }
  const rankByName = new Map(users.map(u => [u.role.name, roleRank(u.role.id)]));
  rows.sort((a, b) => (rankByName.get(a[1].text) ?? 4) - (rankByName.get(b[1].text) ?? 4));
  const columns: ReportColumn[] = ["Level", "Role", "Division / team", "User / manager", "KPI", "Actual", "Target", "Attainment", "Status"].map((label, i) => ({ key: String(i), label, kind: "text" }));
  const failures = first.roles.filter((_, i) => roleResults[i].status === "rejected");
  return <>{header}
    <form method="get" action={base} className="mb-4 flex flex-wrap items-end gap-3">
      <label className="text-sm">Month<input type="month" name="month" defaultValue={first.month} required className="ml-2 rounded border border-rule px-3 py-2" /></label>
      <button className="rounded border border-rule px-3 py-2 text-sm" type="submit">View KPIs</button>
    </form>
    <p className="mb-4 text-sm text-ink-3">{measured.size} users with KPI results across {cards.length} roles. Company totals are shown separately for each role; shared team measures should not be added together. KPIs currently come from CRM, including linked Finance results. Other apps do not yet define per-user KPIs.</p>
    {failures.length > 0 && <p role="status" className="mb-4 text-sm text-danger">Results unavailable for: {failures.map(r => r.name).join(", ")}. Refresh to retry.</p>}
    {(teamsResult.status === "rejected" || usersResult.status === "rejected") && <p role="status" className="mb-4 text-sm text-ink-3">The full user directory or team hierarchy could not be loaded. Only available KPI users and teams are shown.</p>}
    {rows.length ? <ReportTable title={`Company KPIs - ${first.month}`} columns={columns} rows={rows} totals={null} canExport={me.permissions?.includes("reports.export") ?? false} /> : <p>No active KPI assignments for this period.</p>}
  </>;
}
