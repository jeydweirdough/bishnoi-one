import type { ReactNode } from "react";
import { getAccount } from "@/src/platform/lib/account";
import { FeaturesProvider } from "@/src/platform/shell/features";

// Every signed-in page of the one app. No bar across the top (decided
// 2026-10-24): each module's pages bring its sidebar, and at the top right its
// own actions, your modules and your account (src/one/one-actions.tsx), as
// before the one app. Pages with no sidebar use src/one/plain-frame.tsx.
// The company's app catalogue switches (step 6) are given to every screen from here.
export default async function AppLayout({ children }: { children: ReactNode }) {
  const account = await getAccount();
  return (
    <div className="min-h-dvh bg-bench">
      <FeaturesProvider features={account.features ?? null}>{children}</FeaturesProvider>
    </div>
  );
}
