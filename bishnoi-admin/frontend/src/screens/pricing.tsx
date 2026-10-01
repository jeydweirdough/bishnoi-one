import { managersOnly } from "../components/gate";
import { PricingRulesEditor, type PricingView } from "../components/pricing-rules";
import { PageHeader } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { load } from "@/src/platform/lib/api";
import type { PricingRules } from "@/src/platform/lib/types";

export const metadata = { title: "Pricing rules" };

const VIEWS: { value: PricingView; label: string }[] = [
  { value: "divisions", label: "Divisions" },
  { value: "types", label: "Price types" },
  { value: "issuers", label: "Guarantee letter issuers" },
  { value: "defaults", label: "New bundles" },
];

export default async function PricingRulesPage({ searchParams }: { params: Promise<Record<string, never>>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const stop = await managersOnly();
  if (stop) return stop;
  const { view: asked } = await searchParams;
  const view = VIEWS.find((v) => v.value === asked)?.value ?? "divisions";
  const data = await load<PricingRules>("/admin/pricing");
  return (
    <>
      <PageHeader title="Pricing rules">
        Which prices each division quotes with, which take guarantee letters, and when Finance must approve. Products and their
        prices are kept in Inventory.
      </PageHeader>
      <div className="mb-4">
        <ToggleLinks current={view} options={VIEWS.map((v) => ({ ...v, href: `/settings/pricing${v.value === "divisions" ? "" : `?view=${v.value}`}` }))} />
      </div>
      <PricingRulesEditor data={data} view={view} />
    </>
  );
}
