import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
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
  const data = await load<AdminUsers>("/admin/users");
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
        Who can sign in to Finance, and the role each one has.
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
  const data = await load<RolesData>("/admin/roles");
  return (
    <>
      <PageHeader
        title="Roles and permissions"
      >
        What each role can see and do in marketing requests, accounting, tax and administration.
      </PageHeader>
      <RolesEditor data={data} />
    </>
  );
}

export const ACTIONS: Record<string, string> = {
  "user.created": "Added a user",
  "user.updated": "Updated user details",
  "user.switched_off": "Deactivated a user",
  "user.switched_on": "Reactivated a user",
  "user.password_reset": "Reset user password",
  "role.created": "Added a new role",
  "role.updated": "Updated role permissions",
  "role.deleted": "Deleted a role",
  "auth.signed_in": "Signed in",
  "user.profile_changed": "Updated their profile",
  "user.password_changed": "Changed their password",
  "fund.released": "Released a cash advance",
  "fund.cancelled": "Cancelled a marketing request",
  "fund.expense_checked": "Reviewed an expense",
  "fund.sent_back": "Returned a liquidation for correction",
  "fund.checked": "Completed a liquidation review",
  "fund.returned": "Recorded a refund",
  "fund.reimbursed": "Recorded a reimbursement",
  "category.created": "Added an expense category",
  "category.updated": "Changed an expense category",
  "account.created": "Added an account",
  "account.updated": "Changed an account",
  "posting.updated": "Changed the default accounts",
  "entry.posted": "Posted a journal entry",
  "entry.reversed": "Reversed a journal entry",
  "tax.profile_updated": "Changed the tax registration",
  "tax.rate_added": "Added a tax rate change",
  "invoice.drafted": "Drafted an invoice",
  "invoice.updated": "Changed a draft invoice",
  "invoice.deleted": "Deleted a draft invoice",
  "invoice.issued": "Issued an invoice",
  "invoice.voided": "Voided an invoice",
  "invoice.paid": "Recorded a payment",
  "invoice.payment_removed": "Reversed a payment",
  "series.created": "Added invoice numbers",
  "series.updated": "Changed invoice numbers",
};

const FILTERS = [
  { key: "", label: "All" },
  { key: "user.", label: "Users" },
  { key: "role.", label: "Roles" },
  { key: "fund.", label: "Marketing requests" },
  { key: "invoice.", label: "Invoices" },
  { key: "entry.", label: "Journal entries" },
  { key: "account.", label: "Accounts" },
  { key: "category.", label: "Expense categories" },
  { key: "tax.", label: "Tax" },
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
  const queryParts = [];
  if (actionParam) queryParts.push(`action=${encodeURIComponent(actionParam)}`);
  if (beforeParam) queryParts.push(`before=${encodeURIComponent(beforeParam)}`);
  queryParts.push("limit=50");
  const qs = queryParts.length > 0 ? `?${queryParts.join("&")}` : "";

  const page = await load<PageData<AuditEntry>>(`/admin/audit${qs}`);
  const last = page.items.at(-1);

  return (
    <>
      <PageHeader
        title="Activity log"
      >
        Every change made in Finance, and who made it.
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
          <Empty title={beforeParam ? "No older entries" : "No activity yet"} icon="auditLog" />
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
