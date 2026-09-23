import { PersonEditor } from "../components/person-editor";
import { PageHeader } from "@/src/platform/ui/sheet";
import { enc, getMe, load } from "@/src/platform/lib/api";
import { loadOrg } from "@/src/platform/lib/org";
import type { AdminUser, RolesPayload } from "@/src/platform/lib/types";

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
      <PageHeader crumbs={[{ href: "/settings/people", label: "People" }]} title={person.fullName}>
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
