import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { SalesRules } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { RulesEditor } from "../components/catalogue/rules-editor";

export const metadata = { title: "Pricing & retention" };

export default async function PricingPage() {
  const me = await getCompanyMe();
  if (!can(me, "products.view")) return <NoAccess what="products" />;
  const rules = await load<SalesRules>("/pricing");
  return (
    <>
      <PageHeader title="Settings">The rules every quote is priced by, and when a quiet customer counts as at risk or lost.</PageHeader>
      <RulesEditor rules={rules} />
    </>
  );
}
