import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { CatalogueProduct, Paged, PromoRow } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { CatalogueTabs } from "../components/catalogue/catalogue-tabs";
import { PromosEditor } from "../components/catalogue/promos-editor";

export const metadata = { title: "Promos" };

export default async function PromosPage() {
  const me = await getCompanyMe();
  if (!can(me, "products.view")) return <NoAccess what="products" />;
  const [promos, products] = await Promise.all([
    load<{ items: PromoRow[]; can: { edit: boolean } }>("/promos"),
    load<Paged<CatalogueProduct>>("/products?active=true&limit=500"),
  ]);
  return (
    <>
      <PageHeader title="Products & services">Promos a rep can pick on a quote line, while they run.</PageHeader>
      <CatalogueTabs me={me} current="/promos" />
      <PromosEditor
        promos={promos.items}
        products={products.items.map((p) => ({ id: p.id, name: p.name, code: p.code }))}
        org={me.org}
        mayEdit={promos.can.edit}
      />
    </>
  );
}
