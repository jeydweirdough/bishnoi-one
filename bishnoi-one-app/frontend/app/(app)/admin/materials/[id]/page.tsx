import { Restricted } from "@/src/modules/admin/components/restricted";
import type { MaterialPage } from "@/src/modules/admin/actions/materials";
import { enc, getMe, load } from "@/src/modules/admin/platform/lib/api";
import { MaterialScreen } from "@/src/modules/admin/screens/material";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: (await load<MaterialPage>(`/admin/materials/${enc(id)}`)).material.title };
  } catch {
    return { title: "Promotional material" };
  }
}

export default async function Page({ params }: { params: Params }) {
  const { id } = await params;
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("materials.view")) return <Restricted what="the promotional materials" />;
  const data = await load<MaterialPage>(`/admin/materials/${enc(id)}`);
  return <MaterialScreen key={data.material.updatedAt} data={data} />;
}
