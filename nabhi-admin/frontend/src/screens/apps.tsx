import { AppsEditor } from "../components/apps-editor";
import { PageHeader } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import type { AppLink } from "@/src/platform/lib/types";

export const metadata = { title: "Apps" };

export default async function AppsPage() {
  const data = await load<{ apps: AppLink[] }>("/admin/apps");
  return (
    <>
      <PageHeader title="Apps">
        The other applications your people use beside Nabhi, and where each one lives. Add one here and it turns up in the sidebar
        of everyone whose role reaches it, already signed in — nobody has to change any code. What an app lets someone do is still
        set in Roles &amp; permissions.
      </PageHeader>
      <AppsEditor apps={data.apps} />
    </>
  );
}
