import { can } from "@/src/platform/lib/access";
import { getCompanyMe } from "@/src/platform/lib/api";
import { AdminDashboard } from "./home-admin";
import { LeadHome } from "./home-lead";
import { SalespersonHome } from "./home-salesperson";

export const metadata = { title: "Home" };

/**
 * Where each role starts:
 * - the Administrator: a dashboard of how the people use the CRM;
 * - a Team Lead (a role that reaches more than its own records, with reports):
 *   their team, what each person did and has to do;
 * - a Salesperson: their own to do, quotes and recent work.
 */
export default async function Home() {
  const me = await getCompanyMe();
  if (me.isOwner) return <AdminDashboard me={me} />;
  if (me.role?.scope !== "own" && can(me, "reports.view")) return <LeadHome me={me} />;
  return <SalespersonHome />;
}
