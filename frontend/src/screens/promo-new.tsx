import { PromoForm } from "../components/promo-form";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { departmentModule, may } from "@/src/platform/lib/module";
import type { InventoryReference, Product } from "@/src/platform/lib/types";

export const metadata = { title: "Add promo" };

export default async function NewPromoPage({ params }: { params: Promise<{ module: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { module } = await params;
  const [mod, me] = await Promise.all([departmentModule(module, "inventory"), getCompanyMe()]);
  const [reference, products] = await Promise.all([
    load<InventoryReference>("/inventory/reference"),
    load<Product[]>("/inventory/products"),
  ]);
  return (
    <>
      <PageHeader crumbs={[{ href: `/m/${module}/promos`, label: "Promos & discounts" }]} title="Add promo" />
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        {may(mod, "create") ? (
          <PromoForm module={module} reference={reference} products={products} org={me.org} />
        ) : (
          <p className="text-ink-2">You can see Inventory but can&apos;t add promos. Ask your admin if you need to.</p>
        )}
      </Sheet>
    </>
  );
}
