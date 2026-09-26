import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { CompanySettings } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { CompanySettingsForm } from "../components/settings/company-settings-form";

export const metadata = { title: "Company and quotes" };

export default async function CompanySettingsPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.settings")) return <NoAccess what="Settings" />;
  const settings = await load<CompanySettings>("/admin/company-settings");
  return (
    <>
      <PageHeader title="Settings">Your business as every screen shows it, and how quotes are numbered and worded.</PageHeader>
      <CompanySettingsForm initial={settings} />
    </>
  );
}
