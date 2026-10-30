import type { ReactNode } from "react";
import { AdminConsoleFrame } from "@/src/one/admin-console/frame";
import { getAccount } from "@/src/platform/lib/account";
import { Empty, Sheet } from "@/src/platform/ui/sheet";

// Bishnoi One Operations (2026-10-30): every company, accounts and operators, services and their
// connections, and troubleshooting, for Bishnoi One's operators only. A company's own settings are in
// its Admin Console (/platform), never here.
export default async function OperationsLayout({ children }: { children: ReactNode }) {
  const me = await getAccount();
  return (
    <AdminConsoleFrame console="operations">
      {me.staff ? (
        children
      ) : (
        <Sheet>
          <Empty icon="apps" title="For Bishnoi One's operators">
            Companies, services and troubleshooting are kept by Bishnoi One&apos;s operators. Your company&apos;s settings are in the Admin Console.
          </Empty>
        </Sheet>
      )}
    </AdminConsoleFrame>
  );
}
