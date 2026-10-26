import { PeopleNotice } from "@/src/platform/ui/people-notice";
import { AuditLog } from "@/src/platform/screens/audit";
import { PageHeader } from "@/src/modules/inventory/platform/ui/sheet";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { RolesEditor, UsersEditor } from "@/src/modules/inventory/components/admin";
import { NoAccess } from "@/src/modules/inventory/components/ui";
import { query } from "@/src/modules/inventory/lib/labels";
import { context, type Search } from "@/src/modules/inventory/lib/page";
import type { AdminUsers, RolesData } from "@/src/modules/inventory/lib/types";

export async function UsersPage() {
  const { me, may, fmt } = await context();
  if (!may("admin.users")) return <NoAccess what="managing users" />;
  const { users: data } = await loadQuery<{ users: AdminUsers }>("query Users { users }", {}, ["users"]);
  const when = Object.fromEntries(data.items.map((u) => [u.id, fmt.whenLabel(u.lastSignInAt).toLowerCase()]));
  return (
    <>
      <PageHeader title="Users and roles">Users who can sign in to Inventory and their roles. Changes apply on the user&apos;s next action.</PageHeader>
      <PeopleNotice own="each person's role in Inventory" />
      <UsersEditor data={data} meId={me.user.id} when={when} />
    </>
  );
}

export async function RolesPage() {
  const { me, may } = await context();
  if (!may("admin.roles")) return <NoAccess what="roles and permissions" />;
  const { roles: data } = await loadQuery<{ roles: RolesData }>("query Roles { roles }", {}, ["roles"]);
  return (
    <>
      <PageHeader title="Users and roles">Each role is a set of permissions by area. Assign each user the role that matches their job.</PageHeader>
      <RolesEditor data={data} />
    </>
  );
}

// What each recorded change was, said plainly. Anything not listed reads from its code.
export const ACTIONS: Record<string, string> = {
  "auth.signed_in": "Signed in",
  "user.created": "Added a user",
  "user.updated": "Updated a user",
  "user.switched_off": "Deactivated a user",
  "user.switched_on": "Activated a user",
  "user.password_reset": "Reset a password",
  "role.created": "Added a role",
  "role.updated": "Updated a role",
  "role.deleted": "Deleted a role",
  "product.created": "Added a product",
  "product.updated": "Updated a product",
  "product.deleted": "Deleted a product",
  "purchase_order.created": "Created a purchase order",
  "purchase_order.placed": "Approved and placed a purchase order",
  "purchase_order.cancelled": "Cancelled a purchase order",
  "purchase_order.closed": "Closed a partially received purchase order",
  "receipt.posted": "Received stock",
  "order.created": "Created an order",
  "order.confirmed": "Confirmed an order (stock reserved)",
  "order.picking": "Started picking an order",
  "order.issued": "Issued an order",
  "order.cancelled": "Cancelled an order",
  "transfer.created": "Created a transfer",
  "transfer.requested": "Requested a transfer",
  "transfer.approved": "Approved a transfer",
  "transfer.dispatched": "Dispatched a transfer",
  "transfer.received": "Received a transfer",
  "transfer.cancelled": "Cancelled a transfer",
  "adjustment.posted": "Posted an adjustment",
  "adjustment.submitted": "Submitted an adjustment for approval",
  "adjustment.approved": "Approved an adjustment",
  "adjustment.rejected": "Rejected an adjustment",
  "count.started": "Started a count",
  "count.submitted": "Submitted a count",
  "count.approved": "Approved a count",
};

const FILTERS = [
  { key: "", label: "All" },
  { key: "product.", label: "Products" },
  { key: "purchase_order.", label: "Purchasing" },
  { key: "receipt.", label: "Receiving" },
  { key: "order.", label: "Orders" },
  { key: "transfer.", label: "Transfers" },
  { key: "adjustment.", label: "Adjustments" },
  { key: "count.", label: "Counts" },
  { key: "user.", label: "Users" },
  { key: "role.", label: "Roles" },
];

const TARGETS: Record<string, string> = { product: "/inventory/products", supplier: "/inventory/suppliers", warehouse: "/inventory/warehouses" };

/** The activity log: the shared one (src/platform/screens/audit.tsx), with Inventory's words, filters and record links. */
export async function AuditPage({ searchParams }: { searchParams: Search }) {
  const { may } = await context();
  if (!may("admin.audit")) return <NoAccess what="the activity log" />;
  return (
    <AuditLog
      searchParams={searchParams}
      settings={{ words: ACTIONS, filters: FILTERS, targets: TARGETS, about: "User actions, newest first. Changed fields are listed without their values. Stock changes are recorded in stock movements." }}
    />
  );
}
