import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, loadQuery } from "@/src/platform/lib/api";
import { RolesEditor, UsersEditor } from "../components/admin";
import type { AdminUsers, AuditEntry, PageData, RolesData } from "@/src/lib/types";


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

export async function AuditPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
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
  const s = await searchParams;
  const actionParam = typeof s?.action === "string" ? s.action : "";
  const beforeParam = typeof s?.before === "string" ? s.before : "";
  const { audit: page } = await loadQuery<{ audit: PageData<AuditEntry> }>(
    `query Audit($action: String, $before: Int) { audit(action: $action, before: $before, limit: 50) }`,
    { ...(actionParam ? { action: actionParam } : {}), ...(beforeParam ? { before: Number(beforeParam) } : {}) },
    ["audit"],
  );
  const last = page.items.at(-1);

  return (
    <>
      <PageHeader
        title="Activity log"
      >
        Every change made in Bishnoi One Admin, and who made it.
      </PageHeader>
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        <span className="text-meta font-semibold text-ink-2 mr-1">Show:</span>
        {FILTERS.map((f) => {
          const active = actionParam === f.key;
          return (
            <Link
              key={f.key}
              href={`/admin/audit${f.key ? `?action=${f.key}` : ""}`}
              className={`rounded-full px-3 py-1 text-meta font-medium transition-colors ${
                active
                  ? "bg-hema text-white"
                  : "border border-rule-strong bg-sheet text-ink-2 hover:bg-bench"
              }`}
            >
              {f.label}
            </Link>
          );
        })}
      </div>
      <Sheet className="px-5 pt-2 pb-3">
        {page.items.length === 0 ? (
          <Empty title={beforeParam ? "Nothing older" : "Nothing recorded yet"} icon="auditLog" />
        ) : (
          <ol className="divide-y divide-rule">
            {page.items.map((e) => (
              <li key={e.id} className="grid gap-x-4 gap-y-0.5 py-3 sm:grid-cols-[12rem_minmax(0,1fr)]">
                <time dateTime={e.at} className="text-meta text-ink-3 tabular-nums">
                  {new Date(e.at).toLocaleString()}
                </time>
                <div className="min-w-0">
                  <p className="text-sm text-ink">
                    <span className="font-semibold">{ACTIONS[e.action] ?? e.action.replaceAll(/[._]/g, " ")}</span>
                    {e.target && <span className="text-ink-2 font-medium"> · {e.target}</span>}
                  </p>
                  <p className="text-meta text-ink-3">
                    by {e.actor}
                    {e.fields && e.fields.length > 0 && <> · changed {e.fields.join(", ")}</>}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Sheet>
      {(page.more || beforeParam) && (
        <div className="mt-4 flex gap-2">
          {beforeParam && (
            <LinkButton
              href={`/admin/audit${actionParam ? `?action=${actionParam}` : ""}`}
              size="sm"
              variant="quiet"
            >
              Newest
            </LinkButton>
          )}
          {page.more && last && (
            <LinkButton
              href={`/admin/audit?before=${last.id}${actionParam ? `&action=${actionParam}` : ""}`}
              size="sm"
            >
              Older
            </LinkButton>
          )}
        </div>
      )}
    </>
  );
}
