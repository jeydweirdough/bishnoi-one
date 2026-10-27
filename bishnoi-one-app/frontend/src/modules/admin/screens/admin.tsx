import { PeopleNotice } from "@/src/platform/ui/people-notice";
import { AuditLog } from "@/src/platform/screens/audit";
import { PageHeader, Sheet } from "@/src/modules/admin/platform/ui/sheet";
import { getCompanyMe, loadQuery } from "@/src/modules/admin/platform/lib/api";
import { RolesEditor, UsersEditor } from "@/src/modules/admin/components/admin";
import type { AdminUsers, RolesData } from "@/src/modules/admin/lib/types";


export async function UsersPage() {
  const me = await getCompanyMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("admin.users")) {
    return (
      <Sheet className="p-8 text-center">
        <h2 className="text-base font-semibold text-ink">Access restricted</h2>
        <p className="mt-1 text-sm text-ink-3">Your role does not have permission to manage users.</p>
      </Sheet>
    );
  }
  const data = (await loadQuery<{ users: AdminUsers }>("query Users { users }", {}, ["users"])).users;
  const when = Object.fromEntries(
    data.items.map((u) => [
      u.id,
      u.lastSignInAt ? new Date(u.lastSignInAt).toLocaleDateString() : "never",
    ]),
  );
  return (
    <>
      <PageHeader
        title="Users"
      >
        Who can sign in to Bishnoi One Admin, and the role each one has.
      </PageHeader>
      <PeopleNotice own="each person's role in Admin" />
      <UsersEditor data={data} meId={me.user.id} when={when} />
    </>
  );
}

export async function RolesPage() {
  const me = await getCompanyMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("admin.roles")) {
    return (
      <Sheet className="p-8 text-center">
        <h2 className="text-base font-semibold text-ink">Access restricted</h2>
        <p className="mt-1 text-sm text-ink-3">Your role cannot change roles and permissions.</p>
      </Sheet>
    );
  }
  const data = (await loadQuery<{ roles: RolesData }>("query Roles { roles }", {}, ["roles"])).roles;
  return (
    <>
      <PageHeader
        title="Roles and permissions"
      >
        What each role can see and do in permits, expatriates, documents, properties, office requests and administration.
      </PageHeader>
      <RolesEditor data={data} />
    </>
  );
}

export const ACTIONS: Record<string, string> = {
  "user.created": "Added a person",
  "user.updated": "Updated user details",
  "user.switched_off": "Switched a person off",
  "user.switched_on": "Switched a person back on",
  "user.password_reset": "Reset user password",
  "auth.signed_in": "Signed in",
  "user.profile_changed": "Updated their profile",
  "user.password_changed": "Changed their password",
  "role.created": "Added a new role",
  "role.updated": "Updated role permissions",
  "role.deleted": "Deleted a role",
  "permit.created": "Recorded compliance permit",
  "permit.updated": "Updated permit record",
  "permit.deleted": "Deleted permit record",
  "immigration.created": "Recorded visa/ACR document",
  "immigration.updated": "Updated immigration record",
  "immigration.deleted": "Deleted immigration record",
  "document.created": "Filed corporate document",
  "document.updated": "Updated corporate document",
  "document.deleted": "Deleted corporate document",
  "property.created": "Registered lease/property",
  "property.updated": "Updated property details",
  "property.deleted": "Deleted property record",
  "ticket.created": "Raised office ticket",
  "ticket.updated": "Updated office ticket",
  "ticket.resolved": "Resolved office ticket",
  "ticket.deleted": "Deleted office ticket",
};

const FILTERS = [
  { key: "", label: "Everything" },
  { key: "user.", label: "People" },
  { key: "role.", label: "Roles" },
  { key: "permit.", label: "Permits" },
  { key: "immigration.", label: "Expatriates" },
  { key: "document.", label: "Documents" },
  { key: "property.", label: "Properties" },
  { key: "ticket.", label: "Office requests" },
];

/** The activity log: the shared one (src/platform/screens/audit.tsx), with this module's words and filters. */
export async function AuditPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("admin.audit")) {
    return (
      <Sheet className="p-8 text-center">
        <h2 className="text-base font-semibold text-ink">Access restricted</h2>
        <p className="mt-1 text-sm text-ink-3">Your role does not have permission to view the activity log.</p>
      </Sheet>
    );
  }
  return <AuditLog searchParams={searchParams} settings={{ words: ACTIONS, filters: FILTERS }} />;
}
