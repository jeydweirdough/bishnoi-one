import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { getAccount } from "@/src/platform/lib/account";
import { FeaturesProvider } from "@/src/platform/shell/features";
import { TwoStepReminder } from "@/src/one/two-step-reminder";

// Every signed-in page of the one app. No bar across the top (decided
// 2026-10-24): each module's pages bring its sidebar, and at the top right its
// own actions, your modules and your account (src/one/one-actions.tsx), as
// before the one app. Pages with no sidebar use src/one/plain-frame.tsx.
// The company's app catalogue switches (step 6) are given to every screen from here, and to an
// operator the companies they can switch to (the sidebar's company switcher, decided 2026-10-29).
export default async function AppLayout({ children }: { children: ReactNode }) {
  const account = await getAccount();
  // Before anything else (2026-10-30): their own password for a handed-over one, and two-step sign-in where it's owed.
  if (account.mustChangePassword || account.twoStep?.needed) redirect("/login/first");
  return (
    <div className="min-h-dvh bg-bench">
      {account.twoStep?.suggested && <TwoStepReminder />}
      <FeaturesProvider features={account.features ?? null} companies={account.staff ? account.companies : null}>{children}</FeaturesProvider>
    </div>
  );
}
