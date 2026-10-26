import { notFound } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";
import { myModules } from "@/src/one/mine";
import { ReportPage as crm } from "@/src/modules/crm/screens/reports";
import { ReportPage as finance } from "@/src/modules/finance/screens/reports";
import { ReportPage as admin } from "@/src/modules/admin/screens/reports";
import { ReportPage as inventory } from "@/src/modules/inventory/screens/reports";
import { ReportPage as pharmacy } from "@/src/modules/pharmacy/screens/reports";

const pages = { crm, finance, admin, inventory, pharmacy };
export default async function CentralReport({ params, searchParams }: {
  params: Promise<{ module: string; key: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { module, key } = await params;
  const account = await getAccount();
  if (!account.isCompanyAdmin || !Object.hasOwn(pages, module) || !myModules(account).some(m => m.key === module)) notFound();
  const Page = pages[module as keyof typeof pages];
  return <Page params={Promise.resolve({ key })} searchParams={searchParams} reportsBase={`/platform/reports/${module}`} />;
}
