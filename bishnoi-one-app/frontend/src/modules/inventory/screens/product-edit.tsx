import { PageHeader } from "@/src/modules/inventory/platform/ui/sheet";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { ProductForm } from "@/src/modules/inventory/components/product-form";
import { NoAccess } from "@/src/modules/inventory/components/ui";
import { canAddFrom, context, type Params, type Search } from "@/src/modules/inventory/lib/page";
import { referenceOf } from "@/src/modules/inventory/lib/reference";
import type { Product, ProductRow, Reference } from "@/src/modules/inventory/lib/types";

// Adding a product, and changing one: the same form.

type FormData = { reference: Pick<Reference, "brands" | "categories" | "suppliers" | "units">; all: ProductRow[]; product?: Product };

/** The form's lists and the products a new one could be a variant of, with the product being changed, in one request. */
async function formData(id?: string) {
  const data = await loadQuery<FormData>(
    `query ProductForm($id: String!, $editing: Boolean!) { ${referenceOf("brands", "categories", "suppliers", "units")} all: products(status: "all") product(id: $id) @include(if: $editing) }`,
    { id: id ?? "", editing: Boolean(id) },
    id ? ["reference", "all", "product"] : ["reference", "all"],
  );
  // Only a product that isn't itself a variant can have variants.
  const parents = data.all.filter((p) => !p.parentId).map((p) => ({ id: p.id, name: p.name, sku: p.sku }));
  return { ref: data.reference, parents, product: data.product };
}

export async function NewProductPage({ searchParams }: { searchParams: Search }) {
  const { me, may } = await context();
  if (!may("products.create")) return <NoAccess what="adding products" />;
  const { parent } = await searchParams;
  const { ref, parents } = await formData();
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/products", label: "Items" }]} title="New item">
        Product details, pricing, reorder levels and tracking. Stock is added through goods receipts.
      </PageHeader>
      <ProductForm org={me.org} reference={ref} parents={parents} locked={false} canAdd={canAddFrom(may)} preset={{ parentId: typeof parent === "string" ? parent : undefined }} />
    </>
  );
}

export async function EditProductPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, may } = await context();
  if (!may("products.edit")) return <NoAccess what="editing products" />;
  const { ref, parents, product: found } = await formData(id);
  const product = found as Product;
  // Tracking and unit are fixed once stock has moved (the API says so too).
  const locked = product.recentMovements.length > 0;
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/products", label: "Items" }, { href: `/inventory/products/${product.id}`, label: product.name }]} title={`Edit ${product.name}`} />
      <ProductForm key={product.updatedAt} org={me.org} reference={ref} product={product} parents={parents} locked={locked} canAdd={canAddFrom(may)} />
    </>
  );
}
