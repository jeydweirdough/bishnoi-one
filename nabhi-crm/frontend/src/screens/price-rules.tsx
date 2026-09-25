import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { CatalogueProduct, Paged, SalesRules } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { PriceGroupsEditor, PriceRulesEditor } from "../components/catalogue/price-rules-editor";
import type { PriceRules } from "../components/catalogue/price-rules-types";
import { ProcedureEditor } from "../components/catalogue/procedure-editor";
import { SettingsTabs } from "../components/settings/settings-tabs";

export const metadata = { title: "Price rules" };

/**
 * Price rules (benchmarks/decisions.md, D4): the order a quote line is priced
 * in, the price groups customers can be in, and the dated rules. New quotes
 * are priced this way; quotes already made keep their prices.
 */
export default async function PriceRulesPage() {
  const me = await getCompanyMe();
  if (!can(me, "products.view")) return <NoAccess what="products" />;
  const [rules, products, sales] = await Promise.all([
    load<PriceRules>("/pricing/rules"),
    load<Paged<CatalogueProduct>>("/products?active=true&limit=500"),
    load<SalesRules>("/pricing"),
  ]);
  const types = sales.priceTypes.filter((t) => t.isActive && t.entry === "list").map((t) => ({ code: t.code, name: t.name }));
  return (
    <>
      <PageHeader title="Settings">How every quote line is priced, in order. New quotes follow it; quotes already made keep their prices.</PageHeader>
      <SettingsTabs me={me} current="/admin/settings/price-rules" />
      <div className="space-y-6">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="pricing">How a line is priced</SectionTitle>
          <div className="mt-3">
            <ProcedureEditor key={JSON.stringify(rules.procedure) + rules.pricesIncludeTax} rules={rules} />
          </div>
        </Sheet>
        <section className="space-y-2">
          <SectionTitle icon="customers">Price groups</SectionTitle>
          <p className="max-w-[65ch] text-meta text-ink-3">Kinds of customer priced alike. A customer is put in one on its own page.</p>
          <PriceGroupsEditor rules={rules} />
        </section>
        <section className="space-y-2">
          <SectionTitle icon="promos">Rules</SectionTitle>
          <p className="max-w-[65ch] text-meta text-ink-3">
            Each applies between its dates. When several could apply to a line, the most specific wins: one product and one group, then one product,
            then one group, then everything.
          </p>
          <PriceRulesEditor rules={rules} products={products.items.map((p) => ({ id: p.id, name: p.name, code: p.code }))} types={types} org={me.org} />
        </section>
      </div>
    </>
  );
}
