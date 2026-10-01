import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe } from "@/src/platform/lib/api";
import { NoAccess } from "../components/admin/words";
import { ImportWizard } from "../components/import/import-wizard";

export const metadata = { title: "Import products" };

export default async function ProductsImportPage() {
  const me = await getCompanyMe();
  if (!can(me, "products.create") || !can(me, "products.edit")) return <NoAccess what="importing products" />;
  return (
    <>
      <PageHeader title="Import products" crumbs={[{ href: "/products", label: "Products" }]}>
        Products and their prices from a spreadsheet: new ones added, ones already here (same code) updated.
      </PageHeader>
      <ImportWizard kind="products" back="/products" />
    </>
  );
}
