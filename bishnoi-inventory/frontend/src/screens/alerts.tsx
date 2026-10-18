import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { getFrame } from "@/src/platform/lib/api";
import { AlertList } from "../components/alerts";
import { NoAccess } from "../components/ui";
import { context } from "../lib/page";
import type { Alert } from "../lib/types";

export const metadata = { title: "Alerts" };

export default async function AlertsPage() {
  const { may, me } = await context();
  if (!may("dashboard.view")) return <NoAccess what="alerts" />;
  // The sidebar's counts already read them: the same request.
  const alerts = ((await getFrame()).alerts ?? []) as Alert[];
  const warn = (me as unknown as { settings?: { expiryWarningDays: number } }).settings?.expiryWarningDays ?? 90;
  return (
    <>
      <PageHeader title="Alerts">
        Raised automatically as stock moves: low and out-of-stock items, batches expired or expiring within {warn} days, and documents
        pending action by your role.
      </PageHeader>
      <Sheet className="px-5 pt-2 pb-3">
        <AlertList alerts={alerts} />
      </Sheet>
    </>
  );
}
