import { ProductForm } from "../components/product-form";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { departmentModule, may } from "@/src/platform/lib/module";
import type { InventoryReference } from "@/src/platform/lib/types";

export const metadata = { title: "Add product" };

export default async function NewProductPage({ params }: { params: Promise<{ module: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { module } = await params;
  const [mod, me] = await Promise.all([departmentModule(module, "inventory"), getCompanyMe()]);
  const reference = await load<InventoryReference>("/inventory/reference");
  return (
    <>
      <PageHeader crumbs={[{ href: `/m/${module}/products`, label: "Products & prices" }]} title="Add product" />
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        {may(mod, "create") ? (
          <ProductForm module={module} reference={reference} org={me.org} />
        ) : (
          <p className="text-ink-2">You can see Inventory but can&apos;t add products. Ask your admin if you need to.</p>
        )}
      </Sheet>
    </>
  );
}
