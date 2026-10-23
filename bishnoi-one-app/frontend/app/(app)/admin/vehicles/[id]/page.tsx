import { Restricted } from "@/src/modules/admin/components/restricted";
import { KINDS } from "@/src/modules/admin/components/operations/kinds";
import { getMe } from "@/src/modules/admin/platform/lib/api";
import { readRecord } from "@/src/modules/admin/lib/reads";
import { OperationRecord } from "@/src/modules/admin/screens/operation-record";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: KINDS["vehicles"].name((await readRecord("vehicles", id)).record) };
  } catch {
    return { title: KINDS["vehicles"].title };
  }
}

export default async function Page({ params }: { params: Params }) {
  const { id } = await params;
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("vehicles.view")) return <Restricted what="the vehicles" />;
  const data = await readRecord("vehicles", id);
  return <OperationRecord path="vehicles" data={data} can={{ edit: may("vehicles.edit"), delete: may("vehicles.delete") }} />;
}
