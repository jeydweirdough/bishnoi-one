import { ProductForm } from "../components/product-form";
import { SwitchActive } from "../components/switch-active";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { departmentModule, may } from "@/src/platform/lib/module";
import type { InventoryReference, Product } from "@/src/platform/lib/types";

export async function generateMetadata({ params }: { params: Promise<{ module: string; id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { id } = await params;
  const product = await load<Product>(`/inventory/products/${enc(id)}`);
  return { title: product.name };
}

export default async function ProductPage({ params }: { params: Promise<{ module: string; id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { module, id } = await params;
  const [mod, me] = await Promise.all([departmentModule(module, "inventory"), getCompanyMe()]);
  const fmt = makeFormat(me.org);
  const [product, reference] = await Promise.all([
    load<Product>(`/inventory/products/${enc(id)}`),
    load<InventoryReference>("/inventory/reference"),
  ]);
  const canEdit = may(mod, "edit");
  return (
    <>
      <PageHeader
        crumbs={[{ href: `/m/${module}/products`, label: "Products & prices" }]}
        title={product.name}
        actions={canEdit && <SwitchActive kind="product" id={product.id} name={product.name} active={product.isActive} />}
      >
        {product.isActive ? "On sale." : "Switched off: reps can't quote it."} Last changed {fmt.whenLabel(product.updatedAt).toLowerCase()}.
      </PageHeader>
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        {/* Keyed on the last change so a save shows the stored values. */}
        <ProductForm key={product.updatedAt} module={module} reference={reference} product={product} canEdit={canEdit} org={me.org} />
      </Sheet>
    </>
  );
}
