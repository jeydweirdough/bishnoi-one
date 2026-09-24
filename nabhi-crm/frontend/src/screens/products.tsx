import { Upload } from "lucide-react";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { CatalogueProduct, Paged, SalesRules } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { CatalogueTabs } from "../components/catalogue/catalogue-tabs";
import { ProductsEditor } from "../components/catalogue/products-editor";
import { Filters, Pager } from "../components/crm/list-controls";
import { formLayout } from "../components/extra/load";

export const metadata = { title: "Products" };

const SIZE = 100;
type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function ProductsPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "products.view")) return <NoAccess what="products" />;
  const params = await searchParams;
  const [q, active] = [one(params.q), one(params.active)];
  const page = Math.max(1, Number(one(params.page)) || 1);
  const query = new URLSearchParams({ limit: String(SIZE), offset: String((page - 1) * SIZE) });
  if (q) query.set("q", q);
  if (active) query.set("active", active);
  const [list, rules, layout] = await Promise.all([
    load<Paged<CatalogueProduct> & { missingPrices: number }>(`/products?${query}`),
    load<SalesRules>("/pricing"),
    formLayout("product"),
  ]);
  const here = new URLSearchParams(Object.entries({ q, active }).filter(([, v]) => v));

  return (
    <>
      <PageHeader
        title="Products & services"
        actions={
          can(me, "products.create") &&
          can(me, "products.edit") && (
            <LinkButton href="/products/import" icon={<Upload className="size-4" aria-hidden />}>
              Import
            </LinkButton>
          )
        }
      >
        What you sell and what it costs at each price type. Quotes are priced from here, and each team may set its own prices over these.
        {list.missingPrices > 0 && (
          <span className="mt-1 block text-danger">
            {list.missingPrices} {list.missingPrices === 1 ? "product is" : "products are"} missing a price, so {list.missingPrices === 1 ? "it" : "they"} can&apos;t be
            quoted at every price type.
          </span>
        )}
      </PageHeader>
      <CatalogueTabs me={me} current="/products" />
      <Filters
        search="Name, code or generic name"
        selects={[
          {
            name: "active",
            label: "Showing",
            options: [
              { value: "", label: "Every product" },
              { value: "true", label: "On sale" },
              { value: "false", label: "Switched off" },
            ],
          },
        ]}
      />
      <ProductsEditor products={list.items} priceTypes={rules.priceTypes} org={me.org} mayCreate={can(me, "products.create")} layout={layout} />
      <Pager total={list.total} page={page} size={SIZE} base={`/products${here.size ? `?${here}` : ""}`} />
    </>
  );
}
