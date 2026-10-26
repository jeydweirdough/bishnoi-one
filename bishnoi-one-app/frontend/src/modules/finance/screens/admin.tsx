import { PeopleNotice } from "@/src/platform/ui/people-notice";
import { AuditLog } from "@/src/platform/screens/audit";
import { PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { RolesEditor, UsersEditor } from "@/src/modules/finance/components/admin";
import type { AdminUsers, RolesData } from "@/src/modules/finance/lib/types";


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
      <PeopleNotice own="each person's e-signature and calendar" />
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
