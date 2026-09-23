import { PromoForm } from "../components/promo-form";
import { SwitchActive } from "../components/switch-active";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { promoTerms } from "@/src/platform/lib/labels";
import { makeFormat } from "@/src/platform/lib/format";
import { departmentModule, may } from "@/src/platform/lib/module";
import type { InventoryReference, Product, Promo } from "@/src/platform/lib/types";

export async function generateMetadata({ params }: { params: Promise<{ module: string; id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { id } = await params;
  const promo = await load<Promo>(`/inventory/promos/${enc(id)}`);
  return { title: promo.name };
}

export default async function PromoPage({ params }: { params: Promise<{ module: string; id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { module, id } = await params;
  const [mod, me] = await Promise.all([departmentModule(module, "inventory"), getCompanyMe()]);
  const fmt = makeFormat(me.org);
  const [promo, reference, products] = await Promise.all([
    load<Promo>(`/inventory/promos/${enc(id)}`),
    load<InventoryReference>("/inventory/reference"),
    load<Product[]>("/inventory/products?state=all"),
  ]);
  const canEdit = may(mod, "edit");
  return (
    <>
      <PageHeader
        crumbs={[{ href: `/m/${module}/promos`, label: "Promos & discounts" }]}
        title={promo.name}
        actions={canEdit && <SwitchActive kind="promo" id={promo.id} name={promo.name} active={promo.isActive} />}
      >
        {promoTerms(fmt, promo)}
        {!promo.isActive && " · switched off"}
      </PageHeader>
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        <PromoForm key={JSON.stringify(promo)} module={module} reference={reference} products={products} promo={promo} canEdit={canEdit} org={me.org} />
      </Sheet>
    </>
  );
}
