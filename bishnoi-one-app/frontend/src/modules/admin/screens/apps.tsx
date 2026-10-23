import { AppsEditor } from "@/src/modules/admin/components/apps-editor";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";
import { load } from "@/src/modules/admin/platform/lib/api";
import type { AppLink } from "@/src/modules/admin/platform/lib/types";

export const metadata = { title: "Apps" };

export default async function AppsPage() {
  const data = await load<{ apps: AppLink[] }>("/admin/apps");
  return (
    <>
      <PageHeader title="Apps">
        The other applications your people use beside Bishnoi One, and where each one lives. Add one here and it turns up in the sidebar
        of everyone whose role reaches it, already signed in — nobody has to change any code. What an app lets someone do is still
        set in Roles &amp; permissions.
      </PageHeader>
      <AppsEditor apps={data.apps} />
    </>
  );
}
