import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";
import { ApiError, apiFor } from "@/src/platform/lib/api";
import { MODULES } from "@/src/platform/lib/modules";
import { moduleCookie } from "@/src/platform/lib/session-cookie";
import { myModules } from "@/src/one/mine";
import { PageHeader } from "@/src/platform/ui/sheet";
import { ReportsIndex } from "@/src/platform/reports/index-view";
import { listSavedReports } from "@/src/platform/reports/custom-actions";
import type { ReportInfo } from "@/src/platform/reports/types";

export const metadata = { title: "Reports Center" };
export default async function ReportsCenter({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const account = await getAccount();
  if (!account.isCompanyAdmin) redirect("/platform");
  const mine = myModules(account);
  const modules = MODULES.filter(m => !m.accountOnly && m.status === "live" && mine.some(g => g.key === m.key));
  const jar = await cookies();
  const missing = modules.find(m => !jar.get(moduleCookie(m.key))?.value);
  if (missing) redirect(`/auth/enter/${missing.key}?next=${encodeURIComponent("/platform/reports")}`);
  const results = await Promise.allSettled(modules.map(async m => {
    const api = apiFor(m.key);
    const reports = m.key === "inventory"
      ? (await api.post<{ data: { reports: ReportInfo[] }; errors?: unknown[] }>("/graphql", { query: "query Reports { reports }" })).data.reports
      : await api.get<ReportInfo[]>(m.key === "crm" || m.key === "pharmacy" ? "/reports" : `/${m.key}/reports`);
    const saved = await listSavedReports(m.key);
    return {
      reports: reports.map(r => ({ ...r, key: `${m.key}/${r.key}`, group: m.label, about: `${r.group} / ${r.about}` })),
      saved: saved.filter(s => reports.some(r => r.key === s.baseKey)).map(s => ({ ...s, baseKey: `${m.key}/${s.baseKey}` })),
    };
  }));
  const expired = results.findIndex(r => r.status === "rejected" && r.reason instanceof ApiError && r.reason.status === 401);
  if (expired !== -1) redirect(`/auth/enter/${modules[expired].key}?next=${encodeURIComponent("/platform/reports")}`);
  const reports = results.flatMap(r => r.status === "fulfilled" ? r.value.reports : []);
  const saved = results.flatMap(r => r.status === "fulfilled" ? r.value.saved : []);
  const unavailable = modules.filter((_, i) => results[i].status === "rejected");
  const search = await searchParams;
  const asked = typeof search.group === "string" ? search.group : "";
  const group = modules.find(m => m.key === asked || m.label === asked)?.label;
  return <>
    <PageHeader title="Reports Center">View reports across your company in one place. Search, filter, customise and export without switching apps.</PageHeader>
    {unavailable.length > 0 && <p role="status" className="mb-4 text-sm text-ink-2">Reports temporarily unavailable: {unavailable.map(m => m.label).join(", ")}. Refresh to try again.</p>}
    <Link href="/platform/reports/kpis" className="mb-5 block rounded-xl border border-rule bg-white px-5 py-4 hover:bg-bench"><strong>Company KPIs</strong><span className="mt-1 block text-sm text-ink-3">All configured roles, divisions, teams and individual users. View monthly actuals, targets and attainment.</span></Link>
    <ReportsIndex reports={reports} savedReports={saved} base="/platform/reports" group={group} />
  </>;
}
