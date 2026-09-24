import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { AlertList } from "../components/alerts";
import { NoAccess } from "../components/ui";
import { context } from "../lib/page";
import type { Alert } from "../lib/types";

export const metadata = { title: "Alerts" };

export default async function AlertsPage() {
  const { may, me } = await context();
  if (!may("dashboard.view")) return <NoAccess what="alerts" />;
  const alerts = await load<Alert[]>("/inventory/alerts");
  const warn = (me as unknown as { settings?: { expiryWarningDays: number } }).settings?.expiryWarningDays ?? 90;
  return (
    <>
      <PageHeader title="Alerts">
        Flagged by themselves, as stock moves: low and out of stock, batches expired or expiring within {warn} days, and documents
        waiting on someone in your role.
      </PageHeader>
      <Sheet className="px-5 pt-2 pb-3">
        <AlertList alerts={alerts} />
      </Sheet>
    </>
  );
}
