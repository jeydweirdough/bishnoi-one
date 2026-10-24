import { PersonEditor } from "@/src/modules/admin/components/person-editor";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";
import { enc, getMe, load } from "@/src/modules/admin/platform/lib/api";
import { loadOrg } from "@/src/modules/admin/platform/lib/org";
import type { AdminUser, RolesPayload } from "@/src/modules/admin/platform/lib/types";

export default async function PersonPage({ params }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { id } = await params;
  const [person, { roles, modules }, divisions, me] = await Promise.all([
    load<AdminUser>(`/admin/users/${enc(id)}`),
    load<RolesPayload>("/admin/roles"),
    loadOrg(),
    getMe(),
  ]);

  return (
    <>
      <PageHeader crumbs={[{ href: "/admin/settings/people", label: "People" }]} title={person.fullName}>
        {person.email}
        {!person.isActive && " · switched off"}
      </PageHeader>
      <PersonEditor
        person={person}
        roles={roles}
        divisions={divisions}
        apps={modules.filter((m) => m.kind === "app")}
        isMe={person.id === me.user.id}
      />
    </>
  );
}
