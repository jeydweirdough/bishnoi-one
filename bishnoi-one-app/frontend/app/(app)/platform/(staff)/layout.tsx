import type { ReactNode } from "react";
import { getAccount } from "@/src/platform/lib/account";
import { Empty, Sheet } from "@/src/platform/ui/sheet";

// The Operations area (step 5): companies, services and operators, for Bishnoi One's operators only.
export default async function StaffOnly({ children }: { children: ReactNode }) {
  const me = await getAccount();
  if (me.staff) return children;
  return (
    <Sheet>
      <Empty icon="apps" title="For Bishnoi One's operators">
        Companies, services and operators are kept by Bishnoi One&apos;s operators. Your company&apos;s settings are under Company.
      </Empty>
    </Sheet>
  );
}
