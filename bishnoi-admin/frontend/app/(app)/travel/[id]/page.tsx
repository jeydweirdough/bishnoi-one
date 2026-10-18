import { Restricted } from "@/src/components/restricted";
import { KINDS } from "@/src/components/operations/kinds";
import { getMe } from "@/src/platform/lib/api";
import { readRecord } from "@/src/lib/reads";
import { OperationRecord } from "@/src/screens/operation-record";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: KINDS["travel"].name((await readRecord("travel", id)).record) };
  } catch {
    return { title: KINDS["travel"].title };
  }
}

export default async function Page({ params }: { params: Params }) {
  const { id } = await params;
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("travel.view")) return <Restricted what="the hotel and flight sponsorships" />;
  const data = await readRecord("travel", id);
  return <OperationRecord path="travel" data={data} can={{ edit: may("travel.edit"), delete: may("travel.delete") }} />;
}
