import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { getAccount } from "@/src/platform/lib/account";
import { FeaturesProvider } from "@/src/platform/shell/features";
import { OneMenuProvider } from "@/src/one/menu/context";
import { buildMenu } from "@/src/one/menu/one-menu";

// Every signed-in page of the one app. No bar across the top (decided
// 2026-10-24): each module's pages bring the shared sidebar, which draws the one menu given here, and at the top right its
// own actions, your modules and your account (src/one/one-actions.tsx), as
// before the one app. Pages with no sidebar use src/one/plain-frame.tsx.
// An operator is given the companies they can switch to from here (the sidebar's company switcher,
// decided 2026-10-29).
export default async function AppLayout({ children }: { children: ReactNode }) {
  const account = await getAccount();
  // Before anything else (2026-10-30): their own password for a handed-over one, and two-step sign-in where it's owed.
  if (account.mustChangePassword || account.twoStep?.needed) redirect("/login/first");
  return (
    <div className="min-h-dvh bg-bench">
      <FeaturesProvider companies={account.staff ? account.companies : null}>
        {/* One menu by work for every page (M4, 2026-11-18), whichever module keeps the page. */}
        <OneMenuProvider menu={buildMenu(account)}>{children}</OneMenuProvider>
      </FeaturesProvider>
    </div>
  );
}
