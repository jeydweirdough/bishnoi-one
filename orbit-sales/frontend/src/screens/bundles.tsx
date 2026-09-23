import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { BundleRow, CatalogueProduct, Paged, SalesRules } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { BundlesEditor } from "../components/catalogue/bundles-editor";
import { CatalogueTabs } from "../components/catalogue/catalogue-tabs";

export const metadata = { title: "Bundles" };

export default async function BundlesPage() {
  const me = await getCompanyMe();
  if (!can(me, "products.view")) return <NoAccess what="products" />;
  const [bundles, products, rules] = await Promise.all([
    load<{ items: BundleRow[]; can: { edit: boolean } }>("/bundles"),
    load<Paged<CatalogueProduct>>("/products?active=true&limit=500"),
    load<SalesRules>("/pricing"),
  ]);
  const first = rules.priceTypes.find((t) => t.isActive && t.entry === "list");
  return (
    <>
      <PageHeader title="Products & services">Sets of products sold together at one price.</PageHeader>
      <CatalogueTabs me={me} current="/bundles" />
      <BundlesEditor
        bundles={bundles.items}
        products={products.items.map((p) => ({ id: p.id, name: p.name, code: p.code, unit: p.unit, prices: p.prices }))}
        firstPrice={first ? { code: first.code, name: first.name } : null}
        org={me.org}
        mayEdit={bundles.can.edit}
      />
    </>
  );
}
