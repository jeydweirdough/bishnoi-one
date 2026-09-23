import { Plus } from "lucide-react";
import { LinkButton } from "@/src/platform/ui/button";
import { Bars } from "@/src/platform/ui/bars";
import { Figure } from "@/src/platform/ui/figure";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { moduleBase } from "@/src/platform/lib/apps";
import { departmentModule, may } from "@/src/platform/lib/module";
import type { InventorySummary } from "@/src/platform/lib/types";

// Inventory's own overview. Sales divisions have none of their own: their
// overview is the workspace's, over every division at once.

export const metadata = { title: "Inventory" };

type Props = {
  params: Promise<{ module: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function Page({ params }: Props) {
  const { module } = await params;
  const mod = await departmentModule(module, "inventory");
  const { counts } = await load<InventorySummary>("/inventory/summary");
  const canAdd = may(mod, "create");
  // Its own pages: "/products" in this app, "/m/inventory/products" in the
  // shell. The screen says which page, not which address.
  const base = moduleBase(module);
  return (
    <>
      <PageHeader
        title={mod.name}
        actions={
          canAdd && (
            <>
              <LinkButton href={`${base}/promos/new`} icon={<Plus className="size-4" aria-hidden />}>
                Add promo
              </LinkButton>
              <LinkButton href={`${base}/products/new`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>
                Add product
              </LinkButton>
            </>
          )
        }
      >
        Products, their prices, and the promos and discounts reps can put on a quote.
      </PageHeader>
      <Sheet className="mb-5 grid divide-y divide-rule sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <Figure label="Products on sale" value={counts.products} href={`${base}/products`} />
        <Figure label="Products missing a price" value={counts.missingPrices} flag href={`${base}/products`} />
        <Figure label="Promos running today" value={counts.runningPromos} href={`${base}/promos`} />
      </Sheet>
      <Sheet className="mb-5 px-5 pt-4 pb-4">
        <SectionTitle icon="products">The catalogue</SectionTitle>
        {/* Priced and unpriced are parts of the same catalogue, so they are two
            bars of one measure rather than two unrelated figures. */}
        <Bars
          rows={[
            { label: "Priced and quotable", value: Math.max(0, counts.products - counts.missingPrices), href: `${base}/products` },
            { label: "Missing a price", value: counts.missingPrices, href: `${base}/products`, flag: true },
            { label: "Promos running today", value: counts.runningPromos, href: `${base}/promos` },
          ]}
        />
      </Sheet>

      <Sheet className="px-5 py-4 text-sm text-ink-2">
        <SectionTitle icon="pricing">Who sees which price</SectionTitle>
        <p className="mt-1 max-w-prose">
          Keep every price a product has here. Each division only ever sees the prices it&apos;s allowed to quote with, as set by
          your admins in Settings → Pricing rules. B2C reps never see a Distributor&apos;s Price, for example.
        </p>
      </Sheet>
    </>
  );
}
