// The CRM's settings in the Admin Console (2026-10-31): company administrators only. The pages are the CRM's
// own (they talk to its API, modules.ts borrowedOf); this gives them the CRM's words and the person's CRM
// permissions, as the CRM's own frame does.
import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";
import { getCompanyMe } from "@/src/platform/lib/api";
import { CanProvider } from "@/src/modules/crm/components/quick-add/can";
import { TermsProvider } from "@/src/modules/crm/components/terms/provider";
import { termsOf } from "@/src/modules/crm/components/terms/terms";

export default async function Layout({ children }: { children: ReactNode }) {
  const account = await getAccount();
  if (!account.isCompanyAdmin) redirect("/crm");
  const me = await getCompanyMe();
  return (
    <TermsProvider terms={termsOf(me)}>
      <CanProvider permissions={me.permissions ?? []}>{children}</CanProvider>
    </TermsProvider>
  );
}
