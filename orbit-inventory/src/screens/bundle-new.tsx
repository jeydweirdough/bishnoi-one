import { BundleForm } from "../components/bundle-form";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { departmentModule, may } from "@/src/platform/lib/module";
import type { InventoryReference, PricingRules, Product } from "@/src/platform/lib/types";

export const metadata = { title: "Add bundle" };

export default async function NewBundlePage({ params }: { params: Promise<{ module: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { module } = await params;
  const [mod, me] = await Promise.all([departmentModule(module, "inventory"), getCompanyMe()]);
  const [reference, products] = await Promise.all([
    load<InventoryReference>("/inventory/reference"),
    load<Product[]>("/inventory/products"),
  ]);
  // Which way a new bundle starts is the company's default, set in Settings ->
  // Pricing. Inventory staff aren't admins, so a failed read just means the
  // form starts on one line, which is the default anyway.
  const rules = await load<PricingRules>("/admin/pricing").catch(() => null);

  return (
    <>
      <PageHeader crumbs={[{ href: `/m/${module}/bundles`, label: "Bundles" }]} title="Add bundle" />
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        {may(mod, "create") ? (
          <BundleForm
            module={module}
            reference={reference}
            products={products}
            startsAsOneLine={rules?.bundlesAsOneLine ?? true}
            org={me.org}
          />
        ) : (
          <p className="text-ink-2">You can see Inventory but can&apos;t add bundles. Ask your admin if you need to.</p>
        )}
      </Sheet>
    </>
  );
}
