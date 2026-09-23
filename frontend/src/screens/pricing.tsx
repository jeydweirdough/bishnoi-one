import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { SalesRules } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { CatalogueTabs } from "../components/catalogue/catalogue-tabs";
import { RulesEditor } from "../components/catalogue/rules-editor";

export const metadata = { title: "Pricing rules" };

export default async function PricingPage() {
  const me = await getCompanyMe();
  if (!can(me, "products.view")) return <NoAccess what="products" />;
  const rules = await load<SalesRules>("/pricing");
  return (
    <>
      <PageHeader title="Products & services">The rules every quote is priced by.</PageHeader>
      <CatalogueTabs current="/pricing" />
      <RulesEditor rules={rules} />
    </>
  );
}
