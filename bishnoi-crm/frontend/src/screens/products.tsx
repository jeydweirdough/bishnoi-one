import { Upload } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { CatalogueProduct, InventoryLink, Paged, SalesRules, StockAnswer } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { ProductsEditor } from "../components/catalogue/products-editor";
import { SyncNow } from "../components/catalogue/stock";
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
  // "missing" is its own question to the API: on sale, but missing a price.
  if (active === "missing") query.set("missing", "true");
  else if (active) query.set("active", active);
  const [list, rules, layout] = await Promise.all([
    load<Paged<CatalogueProduct> & { missingPrices: number; inventory: InventoryLink }>(`/products?${query}`),
    load<SalesRules>("/pricing"),
    formLayout("product"),
  ]);
  const link = list.inventory;
  // Stock is asked for as the page opens, for the products on it that come from Inventory.
  const codes = list.items.filter((p) => p.fromInventory).map((p) => p.code);
  const stock: StockAnswer | null = link.linked && codes.length ? await load<StockAnswer>(`/stock?codes=${encodeURIComponent(codes.join(","))}`) : null;
  const fmt = makeFormat(me.org);
  const here = new URLSearchParams(Object.entries({ q, active }).filter(([, v]) => v));

  return (
    <>
      <PageHeader
        title="Products and services"
        actions={
          <>
            {link.linked && can(me, "products.edit") && <SyncNow />}
            {can(me, "products.create") && can(me, "products.edit") && (
              <LinkButton href="/products/import" icon={<Upload className="size-4" aria-hidden />}>
                Import
              </LinkButton>
            )}
          </>
        }
      >
        {link.linked ? (
          <>
            The products come from Inventory, with their SRP: add and change them there. Here you set the other price types, and each team may set its own
            prices over these.
            <span className={`mt-1 block ${link.error ? "text-danger" : "text-ink-3"}`}>
              {link.error
                ? `${link.error} The list below is from the last time it worked.`
                : link.syncedAt
                  ? `Last brought over: ${fmt.whenLabel(link.syncedAt)}. It's checked again every 15 minutes.`
                  : "Not brought over from Inventory yet."}
              {stock?.error && ` Stock: ${stock.error}`}
            </span>
          </>
        ) : (
          "What you sell and what it costs at each price type. Quotes are priced from here, and each team may set its own prices over these."
        )}
        {list.missingPrices > 0 && (
          <span className="mt-1 block text-danger">
            {list.missingPrices} {list.missingPrices === 1 ? "product is" : "products are"} missing a price, so {list.missingPrices === 1 ? "it" : "they"} can&apos;t be
            quoted at every price type.{" "}
            {active !== "missing" && (
              <Link href="/products?active=missing" className="font-semibold underline">
                Show {list.missingPrices === 1 ? "it" : "them"}
              </Link>
            )}
          </span>
        )}
      </PageHeader>
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
              { value: "missing", label: "Missing a price" },
            ],
          },
        ]}
      />
      <ProductsEditor
        products={list.items}
        priceTypes={rules.priceTypes}
        org={me.org}
        mayCreate={can(me, "products.create") && !link.linked}
        layout={layout}
        stock={link.linked ? (stock?.items ?? {}) : null}
        inventoryUrl={link.linked ? (link.appUrl ?? null) : null}
      />
      <Pager total={list.total} page={page} size={SIZE} base={`/products${here.size ? `?${here}` : ""}`} />
    </>
  );
}
