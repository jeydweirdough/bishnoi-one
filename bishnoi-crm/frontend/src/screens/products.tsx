import { Download, Upload } from "lucide-react";
import Link from "next/link";
import { LinkButton, buttonClass } from "@/src/platform/ui/button";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { Later } from "@/src/platform/ui/later";
import { Bone, ListRows } from "@/src/platform/ui/skeleton";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { CatalogueProduct, InventoryLink, Paged, SalesRules, StockAnswer } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { ProductsEditor } from "../components/catalogue/products-editor";
import { SyncNow } from "../components/catalogue/stock";
import { Filters, Pager } from "../components/crm/list-controls";
import { formLayout } from "../components/extra/load";

function friendlyError(msg: string | null | undefined): string | null {
  if (!msg) return null;
  if (/INVENTORY_API_KEY|INTEGRATION_KEYS|refused the CRM's key/i.test(msg)) {
    return "Unable to sync with Inventory: connection could not be verified. Please contact your system administrator.";
  }
  return msg;
}

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
  // Asked for, not waited on: the title, filters and list card are drawn now and the products fill in.
  const answer = (async () => {
    const [list, rules, layout] = await Promise.all([
      load<Paged<CatalogueProduct> & { missingPrices: number; inventory: InventoryLink }>(`/products?${query}`),
      load<SalesRules>("/pricing"),
      formLayout("product"),
    ]);
    // Stock is asked for as the page opens, for the products on it that come from Inventory.
    const codes = list.items.filter((p) => p.fromInventory).map((p) => p.code);
    const stock: StockAnswer | null = list.inventory.linked && codes.length ? await load<StockAnswer>(`/stock?codes=${encodeURIComponent(codes.join(","))}`) : null;
    return { list, rules, layout, stock, link: list.inventory };
  })();
  const fmt = makeFormat(me.org);
  const here = new URLSearchParams(Object.entries({ q, active }).filter(([, v]) => v));

  return (
    <>
      <PageHeader
        title="Products and services"
        actions={
          <>
            {can(me, "products.edit") && (
              <Later data={answer} fallback={null}>
                {({ link }) => link.linked && <SyncNow />}
              </Later>
            )}
            {/* The list with its prices, as a spreadsheet: edit it and bring it back with Import prices. */}
            <a href="/products/export?format=xlsx" download className={buttonClass("default")}>
              <Download className="size-4" aria-hidden />
              Export
            </a>
            {(can(me, "products.prices") || can(me, "products.edit")) && (
              <LinkButton href="/products/import?kind=prices" icon={<Upload className="size-4" aria-hidden />}>
                Import prices
              </LinkButton>
            )}
            {can(me, "products.create") && can(me, "products.edit") && (
              <Later data={answer} fallback={null}>
                {({ link }) =>
                  !link.linked && (
                    <LinkButton href="/products/import" icon={<Upload className="size-4" aria-hidden />}>
                      Import
                    </LinkButton>
                  )
                }
              </Later>
            )}
          </>
        }
      >
        <Later data={answer} fallback={<Bone className="mt-1 h-3.5 w-96 max-w-full" />}>
          {({ list, link, stock }) => {
            const linkErr = friendlyError(link.error);
            const stockErr = friendlyError(stock?.error);
            return (
              <>
                {link.linked ? (
                  <>
                    The products come from Inventory, with their SRP: add and change them there. Here you set the other price types, and each team may set its own
                    prices over these.
                    <span className={`mt-1 block ${linkErr ? "text-danger" : "text-ink-3"}`}>
                      {linkErr ? (
                        <>
                          {linkErr} The list below is from the last time it worked.
                          {stockErr && stockErr !== linkErr && <span> Stock: {stockErr}</span>}
                        </>
                      ) : (
                        <>
                          {link.syncedAt
                            ? `Last brought over: ${fmt.whenLabel(link.syncedAt)}. It's checked again every 15 minutes.`
                            : "Not brought over from Inventory yet."}
                          {stockErr && <span> Stock: {stockErr}</span>}
                        </>
                      )}
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
              </>
            );
          }}
        </Later>
      </PageHeader>
      <Filters
        search="Name, code or generic name"
        selects={[
          {
            name: "active",
            label: "Showing",
            options: [
              { value: "", label: "All products" },
              { value: "true", label: "On sale" },
              { value: "false", label: "Inactive" },
              { value: "missing", label: "Price missing" },
            ],
          },
        ]}
      />
      <Later
        data={answer}
        fallback={
          <Sheet>
            <ListRows rows={10} />
          </Sheet>
        }
      >
        {({ list, rules, layout, stock, link }) => (
          <>
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
        )}
      </Later>
    </>
  );
}
