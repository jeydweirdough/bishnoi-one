import { Welcome } from "@/src/platform/ui/welcome";
import { redirect } from "next/navigation";
import { greeting } from "@/src/modules/finance/platform/lib/format";
import { PageHeader } from "@/src/modules/finance/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { EditOverviewButton, OverviewBody, OverviewProvider } from "@/src/modules/finance/overview/overview";
import { PricesWaiting } from "@/src/modules/finance/overview/prices";
import type { OverviewData } from "@/src/modules/finance/overview/types";

// Finance's overview: the Living Overview (src/modules/finance/overview, approved 2026-10-31). One lead card
// and up to five cards for each person, worked out by the API from what they may see and do.

export const metadata = { title: "Overview" };

export default async function FinanceHome() {
  const me = await getCompanyMe();
  // A focused role starts in an allowed workspace, without granting dashboard
  // or financial actions merely to make the module's starting page usable.
  if (!me.permissions?.includes("dashboard.view")) {
    if (me.permissions?.includes("sales_orders.view") && me.permissions?.includes("sales_orders.create")) redirect("/finance/sales-orders");
    if (me.permissions?.includes("invoices.view")) redirect("/finance/invoices/zoho");
    if (me.permissions?.includes("sales_orders.view")) redirect("/finance/sales-orders");
  }
  const overview = await load<OverviewData>("/finance/overview?period=month");
  return (
    <OverviewProvider initial={overview} userId={me.user.id}>
      <PageHeader title="Overview" actions={overview.pickable.length > 0 ? <EditOverviewButton /> : undefined}>
        What needs Finance&apos;s action today.
      </PageHeader>
      <Welcome module="finance" name={me.user.fullName.split(" ")[0]} greeting={greeting()} />
      <OverviewBody org={me.org} prices={overview.cards.wait?.prices ? <PricesWaiting /> : null} />
    </OverviewProvider>
  );
}
