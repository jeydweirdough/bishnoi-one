import { Plus } from "lucide-react";
import Link from "next/link";
import { Avatar } from "@/src/platform/ui/avatar";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/bits";
import { RolesEditor } from "../components/roles-editor";
import { PasswordForm, UserForm } from "../components/user-form";
import { pageFor, param, type Search } from "../lib/page";
import type { AdminUser, AuditItem, PermissionArea, RoleOption, RoleRow } from "../lib/types";

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
        actions={
          <LinkButton href="/admin/users/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
            Add person
          </LinkButton>
        }
      >
        {active} active{users.length > active ? ` · ${users.length - active} switched off` : ""}. Everyone here signs in to the Pharmacy only.
      </PageHeader>
      <Sheet>
        {users.length === 0 ? (
          <Empty icon="people" title="No one yet" />
        ) : (
          <ul className="divide-y divide-rule">
            {users.map((u) => (
              <li key={u.id}>
                <Link href={`/admin/users/${u.id}`} className="grid gap-1 px-5 py-3 hover:bg-bench/40 md:grid-cols-[minmax(0,18rem)_minmax(0,1fr)_auto] md:items-center md:gap-5">
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

export async function UserNewPage() {
  const { allowed } = await pageFor("admin.users");
  if (!allowed) return <NoAccess what="managing users" />;
  const { roles } = await load<{ users: AdminUser[]; roles: RoleOption[] }>("/admin/users");
  return (
    <>
      <PageHeader crumbs={[{ href: "/admin/users", label: "Users" }]} title="Add person" />
      <Sheet className="max-w-[50rem] px-5 py-6 sm:px-8">
        <UserForm roles={roles} />
      </Sheet>
    </>
  );
}

export async function UserPage({ params }: { params: Promise<{ id: string }> }) {
  const { me, fmt, allowed } = await pageFor("admin.users");
  if (!allowed) return <NoAccess what="managing users" />;
  const { id } = await params;
  const user = await load<AdminUser & { roles: RoleOption[] }>(`/admin/users/${enc(id)}`);
  return (
    <>
      <PageHeader crumbs={[{ href: "/admin/users", label: "Users" }]} title={user.fullName}>
        {user.isActive ? user.role.name : "Switched off"} · {user.lastSignInAt ? `last signed in ${fmt.whenLabel(user.lastSignInAt).toLowerCase()}` : "never signed in"}
      </PageHeader>
      <div className="max-w-[50rem] space-y-4">
        <Sheet className="px-5 py-6 sm:px-8">
          <UserForm key={`${user.role.id}-${user.isActive}-${user.fullName}`} roles={user.roles} user={user} isMe={user.id === me.user.id} />
        </Sheet>
        <Sheet className="px-5 py-5 sm:px-8">
          <SectionTitle icon="password">Password</SectionTitle>
          <p className="mt-1 mb-3 text-meta text-ink-3">Setting a new one ends every session they have open.</p>
          <PasswordForm userId={user.id} />
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

export async function AuditPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed } = await pageFor("admin.audit");
  if (!allowed) return <NoAccess what="the activity log" />;
  const search = await searchParams;
  const action = param(search, "action");
  const before = param(search, "before");
  const page = await load<{ items: AuditItem[]; more: boolean }>(
    `/admin/audit?limit=50${action ? `&action=${enc(action)}` : ""}${before ? `&before=${enc(before)}` : ""}`,
  );
  return (
    <>
      <PageHeader title="Activity log">Who did what, and when. It names what changed, never the values.</PageHeader>
      <nav aria-label="Filter" className="mb-3 flex flex-wrap gap-1.5">
        {Object.entries(AREAS).map(([key, label]) => (
          <Link
            key={key}
            href={key ? `/admin/audit?action=${enc(key)}` : "/admin/audit"}
            aria-current={key === action ? "true" : undefined}
            className={`rounded-full border px-2.5 py-0.5 text-meta ${key === action ? "border-hema bg-hema-tint font-semibold text-hema" : "border-rule-strong text-ink-2 hover:text-ink"}`}
          >
            {label}
          </Link>
        ))}
      </nav>
      <Sheet>
        {page.items.length === 0 ? (
          <Empty icon="auditLog" title="Nothing logged yet" />
        ) : (
          <ul className="divide-y divide-rule">
            {page.items.map((e) => (
              <li key={e.id} className="grid gap-1 px-5 py-2.5 text-sm md:grid-cols-[10rem_minmax(0,14rem)_minmax(0,1fr)] md:gap-5">
                <span className="text-meta text-ink-3">{fmt.whenLabel(e.at)}</span>
                <span className="truncate text-ink-2">{e.actor}</span>
                <span className="min-w-0">
                  <span className="font-medium text-ink">{e.action.replaceAll("_", " ").replace(".", " · ")}</span>
                  {e.target && <span className="text-ink-2"> — {e.target}</span>}
                  {e.fields.length > 0 && <span className="block text-meta text-ink-3">Changed: {e.fields.join(", ")}</span>}
                </span>
              </li>
            ))}
          </ul>
        )}
        {page.more && (
          <div className="border-t border-rule px-5 py-3 text-right">
            <Link href={`/admin/audit?${action ? `action=${enc(action)}&` : ""}before=${page.items[page.items.length - 1].id}`} className="text-meta font-semibold text-hema hover:underline">
              Older entries
            </Link>
          </div>
        )}
      </Sheet>
    </>
  );
}
