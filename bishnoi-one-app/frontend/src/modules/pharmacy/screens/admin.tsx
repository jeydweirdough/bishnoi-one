import { redirect } from "next/navigation";
import { PeopleNotice } from "@/src/platform/ui/people-notice";
import { AuditLog } from "@/src/platform/screens/audit";
import Link from "next/link";
import { Avatar } from "@/src/modules/pharmacy/platform/ui/avatar";
import { Empty, PageHeader, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { enc, load } from "@/src/modules/pharmacy/platform/lib/api";
import { NoAccess } from "@/src/modules/pharmacy/components/bits";
import { RolesEditor } from "@/src/modules/pharmacy/components/roles-editor";
import { UserForm } from "@/src/modules/pharmacy/components/user-form";
import { pageFor, type Search } from "@/src/modules/pharmacy/lib/page";
import type { AdminUser, PermissionArea, RoleOption, RoleRow } from "@/src/modules/pharmacy/lib/types";

// Administration: the Pharmacy's own users, what each role may do, and the log
// of who did what. Each page asks for its own permission.

export async function UsersPage() {
  const { me, fmt, allowed } = await pageFor("admin.users");
  if (!allowed) return <NoAccess what="managing users" />;
  const { users } = await load<{ users: AdminUser[]; roles: RoleOption[] }>("/admin/users");
  const active = users.filter((u) => u.isActive).length;
  return (
    <>
      <PageHeader
        title="Users"
      >
        {active} active{users.length > active ? ` · ${users.length - active} switched off` : ""}. Everyone here signs in to the Pharmacy only.
      </PageHeader>
      <PeopleNotice own="each pharmacist's licence number" />
      <Sheet>
        {users.length === 0 ? (
          <Empty icon="people" title="No one yet" />
        ) : (
          <ul className="divide-y divide-rule">
            {users.map((u) => (
              <li key={u.id}>
                <Link href={`/pharmacy/admin/users/${u.id}`} className="grid gap-1 px-5 py-3 hover:bg-bench/40 md:grid-cols-[minmax(0,18rem)_minmax(0,1fr)_auto] md:items-center md:gap-5">
                  <span className="flex min-w-0 items-center gap-2.5">
                    <Avatar name={u.fullName} id={u.id} photoAt={null} size="md" className={u.isActive ? "" : "opacity-60"} />
                    <span className="min-w-0">
                      <span className={`block truncate font-semibold ${u.isActive ? "text-hema" : "text-ink-3"}`}>
                        {u.fullName}
                        {u.id === me.user.id && <span className="font-normal text-ink-3"> (you)</span>}
                      </span>
                      <span className="block truncate text-meta text-ink-3">{u.email}</span>
                    </span>
                  </span>
                  <span className="text-meta text-ink-2">
                    <span className="font-medium text-ink">{u.role.name}</span>
                    {u.licenseNo && ` · ${u.licenseNo}`}
                  </span>
                  <span className="text-meta text-ink-3">{!u.isActive ? "Switched off" : u.lastSignInAt ? `Last in ${fmt.whenLabel(u.lastSignInAt)}` : "Never signed in"}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}

/** People are added once for every module, in Bishnoi One's People (R2). */
export async function UserNewPage() {
  redirect("/platform/roles/people");
}

export async function UserPage({ params }: { params: Promise<{ id: string }> }) {
  const { me, fmt, allowed } = await pageFor("admin.users");
  if (!allowed) return <NoAccess what="managing users" />;
  const { id } = await params;
  const user = await load<AdminUser & { roles: RoleOption[] }>(`/admin/users/${enc(id)}`);
  return (
    <>
      <PageHeader crumbs={[{ href: "/pharmacy/admin/users", label: "Users" }]} title={user.fullName}>
        {user.isActive ? user.role.name : "Switched off"} · {user.lastSignInAt ? `last signed in ${fmt.whenLabel(user.lastSignInAt).toLowerCase()}` : "never signed in"}
      </PageHeader>
      <div className="max-w-[50rem] space-y-4">
        <Sheet className="px-5 py-6 sm:px-8">
          <UserForm key={`${user.role.id}-${user.isActive}-${user.fullName}`} roles={user.roles} user={user} isMe={user.id === me.user.id} />
        </Sheet>
      </div>
    </>
  );
}

export async function RolesPage() {
  const { allowed } = await pageFor("admin.roles");
  if (!allowed) return <NoAccess what="managing roles" />;
  const { roles, catalogue } = await load<{ roles: RoleRow[]; catalogue: PermissionArea[] }>("/admin/roles");
  return (
    <>
      <PageHeader title="Roles & permissions">
        Each person has one role. Checking and verifying a prescription is its own permission, apart from dispensing it.
      </PageHeader>
      <RolesEditor roles={roles} catalogue={catalogue} />
    </>
  );
}

const AREAS: Record<string, string> = {
  "": "Everything",
  "prescription.": "Prescriptions",
  "sale.": "Sales",
  "stock.": "Stock",
  "batch.": "Batches",
  "medicine.": "Medicines",
  "user.": "Users",
  "role.": "Roles",
  "auth.": "Sign-ins",
};

/** The activity log: the shared one (src/platform/screens/audit.tsx), with Pharmacy's filters. */
export async function AuditPage({ searchParams }: { searchParams: Search }) {
  const { allowed } = await pageFor("admin.audit");
  if (!allowed) return <NoAccess what="the activity log" />;
  return <AuditLog searchParams={searchParams} settings={{ filters: Object.entries(AREAS).map(([key, label]) => ({ key, label })), peoplePages: true }} />;
}
