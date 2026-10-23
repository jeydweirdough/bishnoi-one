import { Restricted } from "@/src/modules/admin/components/restricted";
import { KINDS } from "@/src/modules/admin/components/operations/kinds";
import { getMe } from "@/src/modules/admin/platform/lib/api";
import { readRecord } from "@/src/modules/admin/lib/reads";
import { OperationRecord } from "@/src/modules/admin/screens/operation-record";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: KINDS["fleet-cards"].name((await readRecord("fleet-cards", id)).record) };
  } catch {
    return { title: KINDS["fleet-cards"].title };
  }
}

export default async function Page({ params }: { params: Params }) {
  const { id } = await params;
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("vehicles.view")) return <Restricted what="the fuel cards" />;
  const data = await readRecord("fleet-cards", id);
  return <OperationRecord path="fleet-cards" data={data} can={{ edit: may("vehicles.edit"), delete: may("vehicles.delete") }} />;
}
