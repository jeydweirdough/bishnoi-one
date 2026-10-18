import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe } from "@/src/platform/lib/api";
import { NoAccess } from "../components/admin/words";
import { ImportWizard } from "../components/import/import-wizard";

export const metadata = { title: "Import products" };

/** Products from a spreadsheet (whoever adds and edits them, when the list isn't Inventory's),
 *  or prices only (?kind=prices: a manager's, sent to Finance for approval). */
export default async function ProductsImportPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  const { kind } = await searchParams;
  const products = can(me, "products.create") && can(me, "products.edit");
  const prices = kind === "prices" || !products;
  if (prices && !(can(me, "products.prices") || can(me, "products.edit"))) return <NoAccess what="importing prices" />;
  if (!prices && !products) return <NoAccess what="importing products" />;
  return (
    <>
      <PageHeader title={prices ? "Import prices" : "Import products"} crumbs={[{ href: "/products", label: "Products" }]}>
        {prices
          ? "Prices for products already here, from a spreadsheet: match its columns to the code and the price types, check, then import. Export the products first to start from today's prices."
          : "Products and their prices from a spreadsheet: new ones added, ones already here (same code) updated."}
      </PageHeader>
      <ImportWizard kind={prices ? "prices" : "products"} back="/products" />
    </>
  );
}
