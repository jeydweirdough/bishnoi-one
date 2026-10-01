import { managersOnly } from "../components/gate";
import { RolesEditor } from "../components/roles-editor";
import { PageHeader } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import type { RolesPayload } from "@/src/platform/lib/types";

export const metadata = { title: "Roles and permissions" };

export default async function RolesPage() {
  const stop = await managersOnly();
  if (stop) return stop;
  const data = await load<RolesPayload>("/admin/roles");
  return (
    <>
      <PageHeader title="Roles and permissions">
        What each role may do in each of the {data.modules.length} modules. Pick a role to change its row.
      </PageHeader>
      <RolesEditor data={data} />
    </>
  );
}
