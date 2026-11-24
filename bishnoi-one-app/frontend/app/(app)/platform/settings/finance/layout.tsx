// Finance's settings in the Admin Console (2026-10-31): company administrators only. The pages are
// Finance's own and talk to its API (modules.ts borrowedOf); one sidebar row, its parts as tabs (2026-11-01).
import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";
import { LinkTabs } from "@/src/platform/ui/link-tabs";
import { FINANCE_TABS } from "@/src/one/admin-console/app-settings";

const SETTINGS_PERMS = ["accounts.manage", "tax.manage", "tax.view", "categories.manage", "invoices.setup"];

export default async function Layout({ children }: { children: ReactNode }) {
  const account = await getAccount();
  const financeApp = account.apps.find((a) => a.key === "finance");
  const canOpenFinanceSettings =
    account.isCompanyAdmin ||
    (Boolean(financeApp) &&
      (financeApp?.permissions == null || SETTINGS_PERMS.some((p) => financeApp.permissions!.includes(p))));
  if (!canOpenFinanceSettings) redirect("/finance");
  return (
    <>
      <LinkTabs label="Finance settings" tabs={FINANCE_TABS} />
      {children}
    </>
  );
}
