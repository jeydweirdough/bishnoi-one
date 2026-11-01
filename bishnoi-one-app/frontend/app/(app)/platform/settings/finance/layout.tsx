// Finance's settings in the Admin Console (2026-10-31): company administrators only. The pages are
// Finance's own and talk to its API (modules.ts borrowedOf); one sidebar row, its parts as tabs (2026-11-01).
import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";
import { LinkTabs } from "@/src/platform/ui/link-tabs";
import { FINANCE_TABS } from "@/src/one/admin-console/app-settings";

export default async function Layout({ children }: { children: ReactNode }) {
  if (!(await getAccount()).isCompanyAdmin) redirect("/finance");
  return (
    <>
      <LinkTabs label="Finance settings" tabs={FINANCE_TABS} />
      {children}
    </>
  );
}
