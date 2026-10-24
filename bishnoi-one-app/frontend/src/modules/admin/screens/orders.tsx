import { managersOnly } from "@/src/modules/admin/components/gate";
import { OrderSettingsEditor } from "@/src/modules/admin/components/order-settings";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/modules/admin/platform/lib/api";
import type { OrderSettings } from "@/src/modules/admin/platform/lib/types";

export const metadata = { title: "Order settings" };

export default async function OrderSettingsPage() {
  const stop = await managersOnly();
  if (stop) return stop;
  const [data, me] = await Promise.all([load<OrderSettings>("/admin/orders"), getCompanyMe()]);
  return (
    <>
      <PageHeader title="Orders">
        What the Orders app offers when an order is raised: its pick-lists, any extra fields, and the rules it follows. Who may take
        each order step is set in Roles &amp; permissions.
      </PageHeader>
      <OrderSettingsEditor data={data} org={me.org} />
    </>
  );
}
