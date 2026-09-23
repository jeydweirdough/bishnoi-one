import { BundleForm } from "../components/bundle-form";
import { SwitchActive } from "../components/switch-active";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { departmentModule, may } from "@/src/platform/lib/module";
import type { Bundle, InventoryReference, Product } from "@/src/platform/lib/types";

export async function generateMetadata({ params }: { params: Promise<{ module: string; id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { id } = await params;
  const bundle = await load<Bundle>(`/inventory/bundles/${enc(id)}`);
  return { title: bundle.name };
}

export default async function BundlePage({ params }: { params: Promise<{ module: string; id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { module, id } = await params;
  const [mod, me] = await Promise.all([departmentModule(module, "inventory"), getCompanyMe()]);
  const fmt = makeFormat(me.org);
  const [bundle, reference, products] = await Promise.all([
    load<Bundle>(`/inventory/bundles/${enc(id)}`),
    load<InventoryReference>("/inventory/reference"),
    load<Product[]>("/inventory/products?state=all"),
  ]);
  const canEdit = may(mod, "edit");
  const items = bundle.items.length === 1 ? "1 product" : `${bundle.items.length} products`;

  return (
    <>
      <PageHeader
        crumbs={[{ href: `/m/${module}/bundles`, label: "Bundles" }]}
        title={bundle.name}
        actions={canEdit && <SwitchActive kind="bundle" id={bundle.id} name={bundle.name} active={bundle.isActive} />}
      >
        {fmt.peso(bundle.priceCentavos)} the set · {items} · shown as {bundle.asOneLine ? "one line" : "its items"}
        {!bundle.isActive && " · switched off"}
      </PageHeader>
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        <BundleForm
          key={JSON.stringify(bundle)}
          module={module}
          reference={reference}
          products={products}
          bundle={bundle}
          canEdit={canEdit}
          org={me.org}
        />
      </Sheet>
    </>
  );
}
