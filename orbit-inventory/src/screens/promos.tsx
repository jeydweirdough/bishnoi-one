import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { load } from "@/src/platform/lib/api";
import { promoTerms } from "@/src/platform/lib/labels";
import { departmentModule, may } from "@/src/platform/lib/module";
import { orgFormat } from "@/src/platform/lib/org";
import type { InventoryReference, Product, Promo } from "@/src/platform/lib/types";

export const metadata = { title: "Promos & discounts" };

const STATES = [
  { value: "current", label: "Running & upcoming" },
  { value: "ended", label: "Ended" },
  { value: "off", label: "Switched off" },
];

const STATE_LABELS: Record<Promo["state"], string> = { running: "Running", upcoming: "Upcoming", ended: "Ended", off: "Off" };

export default async function PromosPage({ params, searchParams }: { params: Promise<{ module: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { module } = await params;
  const search = await searchParams;
  const [mod, fmt] = await Promise.all([departmentModule(module, "inventory"), orgFormat()]);
  const state = STATES.some((s) => s.value === search.state) ? String(search.state) : "current";
  const [promos, products, reference] = await Promise.all([
    load<Promo[]>(`/inventory/promos?state=${state}`),
    load<Product[]>("/inventory/products?state=all"),
    load<InventoryReference>("/inventory/reference"),
  ]);
  const productNames = new Map(products.map((p) => [p.id, p.name]));
  const divisionNames = new Map(reference.divisions.map((d) => [d.code, d.name]));
  const which = (p: Promo) =>
    p.productIds === null
      ? "Every product"
      : p.productIds.length > 2
        ? `${p.productIds.length} products`
        : p.productIds.map((id) => productNames.get(id) ?? "a product").join(", ");
  const when = (p: Promo) => (p.endsOn ? `${fmt.dateLabel(p.startsOn)} – ${fmt.dateLabel(p.endsOn)}` : `From ${fmt.dateLabel(p.startsOn)}`);

  return (
    <>
      <PageHeader
        title="Promos & discounts"
        actions={
          may(mod, "create") && (
            <LinkButton href={`/m/${module}/promos/new`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add promo
            </LinkButton>
          )
        }
      >
        Reps pick one per quote line, from the ones running for their division. Big manual discounts go to Finance.
      </PageHeader>
      <div className="mb-3">
        <ToggleLinks current={state} options={STATES.map((s) => ({ ...s, href: `/m/${module}/promos?state=${s.value}` }))} />
      </div>
      <Sheet>
        {promos.length === 0 ? (
          <Empty icon="promos" title="No promos here">{state === "current" ? "Add a promo and pick the divisions that can use it." : null}</Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {promos.map((p) => (
              <li key={p.id} className="flex flex-wrap items-start justify-between gap-x-6 gap-y-1 px-5 py-3.5">
                <div className="min-w-0">
                  <Link href={`/m/${module}/promos/${p.id}`} className="font-semibold text-hema hover:underline">
                    {p.name}
                  </Link>
                  <p className="text-sm text-ink">{promoTerms(fmt, p)}</p>
                  <p className="text-meta text-ink-3">
                    {which(p)} · {p.divisionCodes.map((c) => divisionNames.get(c) ?? c).join(", ")}
                  </p>
                </div>
                <div className="text-right text-meta text-ink-3">
                  <span className="font-semibold text-ink-2">{STATE_LABELS[p.state]}</span>
                  <span className="block">{when(p)}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
