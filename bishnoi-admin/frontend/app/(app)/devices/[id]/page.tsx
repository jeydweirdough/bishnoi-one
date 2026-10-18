import { Restricted } from "@/src/components/restricted";
import { KINDS } from "@/src/components/operations/kinds";
import { getMe } from "@/src/platform/lib/api";
import { readRecord } from "@/src/lib/reads";
import { OperationRecord } from "@/src/screens/operation-record";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: KINDS["devices"].name((await readRecord("devices", id)).record) };
  } catch {
    return { title: KINDS["devices"].title };
  }
}

export default async function Page({ params }: { params: Params }) {
  const { id } = await params;
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("devices.view")) return <Restricted what="the devices issued" />;
  const data = await readRecord("devices", id);
  return <OperationRecord path="devices" data={data} can={{ edit: may("devices.edit"), delete: may("devices.delete") }} />;
}
