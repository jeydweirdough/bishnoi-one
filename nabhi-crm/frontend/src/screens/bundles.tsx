import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { BundleRow, CatalogueProduct, DivisionOption, Paged, SalesRules } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { BundlesEditor } from "../components/catalogue/bundles-editor";
import { DivisionFilter, inDivision } from "../components/catalogue/division-filter";

export const metadata = { title: "Bundles" };

export default async function BundlesPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "products.view")) return <NoAccess what="products" />;
  const { division } = await searchParams;
  const [bundles, products, rules] = await Promise.all([
    load<{ items: BundleRow[]; teams: DivisionOption[]; can: { edit: boolean } }>("/bundles"),
    load<Paged<CatalogueProduct>>("/products?active=true&limit=500"),
    load<SalesRules>("/pricing"),
  ]);
  const first = rules.priceTypes.find((t) => t.isActive && t.entry === "list");
  const current = typeof division === "string" ? division : "";
  return (
    <>
      <PageHeader title="Products & services">
        Sets of products sold together at one price. Each is for its own divisions: nobody else sees or quotes it.
      </PageHeader>
      <DivisionFilter base="/bundles" teams={bundles.teams} current={current} />
      <BundlesEditor
        bundles={inDivision(bundles.items, current)}
        products={products.items.map((p) => ({ id: p.id, name: p.name, code: p.code, unit: p.unit, prices: p.prices }))}
        teams={bundles.teams}
        firstPrice={first ? { code: first.code, name: first.name } : null}
        org={me.org}
        mayEdit={bundles.can.edit}
      />
    </>
  );
}
