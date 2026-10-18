import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { KpiCatalogue, Paged } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { KpiEditor } from "../components/kpis/kpi-editor";
import { PerformanceTabs } from "./performance-settings";

export const metadata = { title: "Performance" };

export default async function KpiSettingsPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.settings")) return <NoAccess what="choosing what is measured" />;
  const [catalogue, products] = await Promise.all([
    load<KpiCatalogue>("/kpis?all=true"),
    can(me, "products.view") ? load<Paged<{ id: string; name: string }>>("/products?limit=500") : Promise.resolve({ items: [], total: 0 }),
  ]);
  return (
    <>
      <PageHeader title="Settings">
        Performance: what each person&apos;s month is measured by. Pick what the CRM counts, or have it entered by hand; say who it&apos;s for, and from what share of
        the target it counts as on target or slightly behind. Targets are set each month under Targets. The built-in ones keep what they measure but can be renamed,
        retuned or deactivated.
      </PageHeader>
      <PerformanceTabs current="measures" />
      <KpiEditor catalogue={catalogue} products={products.items.map((p) => ({ id: p.id, name: p.name }))} />
    </>
  );
}
