import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { load } from "@/src/platform/lib/api";
import { departmentModule, may } from "@/src/platform/lib/module";
import { orgFormat } from "@/src/platform/lib/org";
import type { Bundle, InventoryReference, Product } from "@/src/platform/lib/types";

export const metadata = { title: "Bundles" };

const STATES = [
  { value: "current", label: "Running & upcoming" },
  { value: "ended", label: "Ended" },
  { value: "off", label: "Switched off" },
];

const STATE_LABELS: Record<Bundle["state"], string> = { running: "Running", upcoming: "Upcoming", ended: "Ended", off: "Off" };

export default async function BundlesPage({ params, searchParams }: { params: Promise<{ module: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { module } = await params;
  const search = await searchParams;
  const [mod, fmt] = await Promise.all([departmentModule(module, "inventory"), orgFormat()]);
  const state = STATES.some((s) => s.value === search.state) ? String(search.state) : "current";
  const [bundles, products, reference] = await Promise.all([
    load<Bundle[]>(`/inventory/bundles?state=${state}`),
    load<Product[]>("/inventory/products?state=all"),
    load<InventoryReference>("/inventory/reference"),
  ]);
  const productNames = new Map(products.map((p) => [p.id, p.name]));
  const divisionNames = new Map(reference.divisions.map((d) => [d.code, d.name]));
  const contents = (b: Bundle) =>
    b.items.length > 3
      ? `${b.items.length} products`
      : b.items.map((i) => `${i.qty} × ${productNames.get(i.productId) ?? "a product"}`).join(", ");
  const when = (b: Bundle) => (b.endsOn ? `${fmt.dateLabel(b.startsOn)} – ${fmt.dateLabel(b.endsOn)}` : `From ${fmt.dateLabel(b.startsOn)}`);

  return (
    <>
      <PageHeader
        title="Bundles"
        actions={
          may(mod, "create") && (
            <LinkButton href={`/m/${module}/bundles/new`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add bundle
            </LinkButton>
          )
        }
      >
        A set of products sold at one price. Reps put one on a quote instead of a product, from the ones running for their division.
      </PageHeader>
      <div className="mb-3">
        <ToggleLinks current={state} options={STATES.map((s) => ({ ...s, href: `/m/${module}/bundles?state=${s.value}` }))} />
      </div>
      <Sheet>
        {bundles.length === 0 ? (
          <Empty icon="promos" title="No bundles here">
            {state === "current" ? "Add a bundle, put products in it, and price the whole set." : null}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {bundles.map((b) => (
              <li key={b.id} className="flex flex-wrap items-start justify-between gap-x-6 gap-y-1 px-5 py-3.5">
                <div className="min-w-0">
                  <Link href={`/m/${module}/bundles/${b.id}`} className="font-semibold text-hema hover:underline">
                    {b.name}
                  </Link>
                  <p className="text-sm text-ink">
                    {fmt.peso(b.priceCentavos)} the set · {b.asOneLine ? "one line" : "its items"}
                  </p>
                  <p className="text-meta text-ink-3">
                    {b.code} · {contents(b)} · {b.divisionCodes.map((c) => divisionNames.get(c) ?? c).join(", ")}
                  </p>
                </div>
                <div className="text-right text-meta text-ink-3">
                  <span className="font-semibold text-ink-2">{STATE_LABELS[b.state]}</span>
                  <span className="block">{when(b)}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
