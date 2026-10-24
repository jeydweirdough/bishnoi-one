import type { ReactNode } from "react";
import { getAccount } from "@/src/platform/lib/account";
import { Empty, Sheet } from "@/src/platform/ui/sheet";

// APIs, companies and accounts are the Platform's own: Bishnoi One's staff only.
export default async function StaffOnly({ children }: { children: ReactNode }) {
  const me = await getAccount();
  if (me.staff) return children;
  return (
    <Sheet>
      <Empty icon="apps" title="For Bishnoi One's staff">
        APIs, companies and accounts are managed by Bishnoi One&apos;s staff. Your company&apos;s roles are under Roles and permissions.
      </Empty>
    </Sheet>
  );
}
