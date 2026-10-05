import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { CatalogueProduct, DivisionOption, Paged, PromoRow } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { DivisionFilter, inDivision } from "../components/catalogue/division-filter";
import { PromosEditor } from "../components/catalogue/promos-editor";

export const metadata = { title: "Promos" };

export default async function PromosPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "products.view")) return <NoAccess what="products" />;
  const { division } = await searchParams;
  const [promos, products] = await Promise.all([
    load<{ items: PromoRow[]; teams: DivisionOption[]; can: { edit: boolean } }>("/promos"),
    load<Paged<CatalogueProduct>>("/products?active=true&limit=500"),
  ]);
  const current = typeof division === "string" ? division : "";
  return (
    <>
      <PageHeader title="Products and services">
        Promos a rep can pick on a quote line, while they run. Each is for its own divisions: nobody else sees or quotes it.
      </PageHeader>
      <DivisionFilter base="/promos" teams={promos.teams} current={current} />
      <PromosEditor
        promos={inDivision(promos.items, current)}
        products={products.items.map((p) => ({ id: p.id, name: p.name, code: p.code }))}
        teams={promos.teams}
        org={me.org}
        mayEdit={promos.can.edit}
      />
    </>
  );
}
