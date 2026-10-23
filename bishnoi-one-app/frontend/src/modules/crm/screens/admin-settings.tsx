import { PageHeader } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { CustomEntity, CustomerType, FormLayout } from "@/src/platform/lib/types";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { FormEditor } from "@/src/modules/crm/components/settings/form-editor";
import type { TeamName } from "@/src/modules/crm/components/admin/teams-for";
import { ENTITY_WORDS } from "@/src/modules/crm/components/settings/words";

export const metadata = { title: "Forms" };

const ENTITIES = Object.keys(ENTITY_WORDS) as CustomEntity[];

export default async function FormsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "admin.settings")) return <NoAccess what="Settings" />;
  const asked = (await searchParams).entity;
  const entity = ENTITIES.find((e) => e === asked) ?? "company";
  const [layout, teams, types] = await Promise.all([
    load<FormLayout>(`/forms/${entity}?all=true`),
    load<TeamName[]>("/team-names"),
    entity === "company" ? load<CustomerType[]>("/customer-types") : Promise.resolve([] as CustomerType[]),
  ]);
  const kinds = types.map((t) => ({ id: t.code, name: t.name, isActive: t.isActive }));
  return (
    <>
      <PageHeader title="Settings">Lay out each form as it reads: drag fields onto the page, group them in sections, and click a field to change it. Everyone gets the form as saved here.</PageHeader>
      <div className="mb-4">
        <ToggleLinks current={entity} options={ENTITIES.map((e) => ({ value: e, label: ENTITY_WORDS[e].many, href: `/crm/admin/settings?entity=${e}` }))} />
      </div>
      <FormEditor key={entity} entity={entity} layout={layout} teams={teams} kinds={kinds} />
    </>
  );
}
