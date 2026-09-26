import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { RolesEditor, UsersEditor } from "../components/admin";
import { Chips, NoAccess } from "../components/ui";
import { param, query, referenceHref } from "../lib/labels";
import { context, type Search } from "../lib/page";
import type { AdminUsers, AuditEntry, Page, RolesData } from "../lib/types";

export async function UsersPage() {
  const { me, may, fmt } = await context();
  if (!may("admin.users")) return <NoAccess what="managing users" />;
  const data = await load<AdminUsers>("/admin/users");
  const when = Object.fromEntries(data.items.map((u) => [u.id, fmt.whenLabel(u.lastSignInAt).toLowerCase()]));
  return (
    <>
      <PageHeader title="Users & roles">Who can sign in to Inventory, and what their role lets them do. A change applies on their next click.</PageHeader>
      <UsersEditor data={data} meId={me.user.id} when={when} />
    </>
  );
}

export async function RolesPage() {
  const { me, may } = await context();
  if (!may("admin.roles")) return <NoAccess what="roles & permissions" />;
  const data = await load<RolesData>("/admin/roles");
  return (
    <>
      <PageHeader title="Users & roles">Each role is a set of permissions, area by area. Give people the role that fits their job.</PageHeader>
      <RolesEditor data={data} />
    </>
  );
}

// What each recorded change was, said plainly. Anything not listed reads from its code.
const ACTIONS: Record<string, string> = {
  "user.created": "Added a person",
  "user.updated": "Changed a person",
  "user.switched_off": "Switched a person off",
  "user.switched_on": "Switched a person back on",
  "user.password_reset": "Set a new password",
  "role.created": "Added a role",
  "role.updated": "Changed a role",
  "role.deleted": "Deleted a role",
  "product.created": "Added a product",
  "product.updated": "Changed a product",
  "product.deleted": "Deleted a product",
  "purchase_order.created": "Wrote up a purchase order",
  "purchase_order.placed": "Approved and placed a purchase order",
  "purchase_order.cancelled": "Cancelled a purchase order",
  "purchase_order.closed": "Closed a part-received purchase order",
  "receipt.posted": "Received stock",
  "order.created": "Wrote up an order",
  "order.confirmed": "Confirmed an order (stock reserved)",
  "order.picking": "Started picking an order",
  "order.issued": "Issued an order",
  "order.cancelled": "Cancelled an order",
  "transfer.created": "Drafted a transfer",
  "transfer.requested": "Requested a transfer",
  "transfer.approved": "Approved a transfer",
  "transfer.dispatched": "Dispatched a transfer",
  "transfer.received": "Received a transfer",
  "transfer.cancelled": "Cancelled a transfer",
  "adjustment.posted": "Posted an adjustment",
  "adjustment.submitted": "Sent an adjustment for approval",
  "adjustment.approved": "Approved an adjustment",
  "adjustment.rejected": "Rejected an adjustment",
  "count.started": "Started a count",
  "count.submitted": "Submitted a count",
  "count.approved": "Approved a count",
};

const FILTERS = [
  { key: "", label: "Everything" },
  { key: "product.", label: "Products" },
  { key: "purchase_order.", label: "Purchasing" },
  { key: "receipt.", label: "Receiving" },
  { key: "order.", label: "Orders" },
  { key: "transfer.", label: "Transfers" },
  { key: "adjustment.", label: "Adjustments" },
  { key: "count.", label: "Counts" },
  { key: "user.", label: "People" },
  { key: "role.", label: "Roles" },
];

const TARGETS: Record<string, string> = { product: "/products", supplier: "/suppliers", warehouse: "/warehouses" };

export async function AuditPage({ searchParams }: { searchParams: Search }) {
  const { may, at } = await context();
  if (!may("admin.audit")) return <NoAccess what="the activity log" />;
  const s = await searchParams;
  const action = FILTERS.find((f) => f.key === param(s, "action"))?.key ?? "";
  const before = param(s, "before");
  const page = await load<Page<AuditEntry>>(`/admin/audit${query({ action, before, limit: 50 })}`);
  const last = page.items.at(-1);
  return (
    <>
      <PageHeader title="Activity log">
        Who did what, newest first. It names the fields that changed, never what they were changed to. Stock itself is traced on the movement trail.
      </PageHeader>
      <Chips label="Show" current={action} options={FILTERS.map((f) => ({ value: f.key, label: f.label, href: `/admin/audit${query({ action: f.key })}` }))} />
      <Sheet className="px-5 pt-2 pb-3">
        {page.items.length === 0 ? (
          <Empty title={before ? "Nothing older" : "Nothing recorded yet"} icon="auditLog" />
        ) : (
          <ol className="divide-y divide-rule">
            {page.items.map((e) => {
              const href = e.targetType && e.targetId ? (referenceHref(e.targetType, e.targetId) ?? (TARGETS[e.targetType] ? `${TARGETS[e.targetType]}/${e.targetId}` : null)) : null;
              return (
                <li key={e.id} className="grid gap-x-4 gap-y-0.5 py-3 sm:grid-cols-[11rem_minmax(0,1fr)]">
                  <time dateTime={e.at} className="text-meta text-ink-3 tabular-nums">{at(e.at)}</time>
                  <div className="min-w-0">
                    <p className="text-sm">
                      <span className="font-semibold">{ACTIONS[e.action] ?? e.action.replaceAll(/[._]/g, " ")}</span>
                      {e.target && <span className="text-ink-2"> · {href ? <Link href={href} className="hover:text-hema hover:underline">{e.target}</Link> : e.target}</span>}
                    </p>
                    <p className="text-meta text-ink-3">by {e.actor}{e.fields.length > 0 && <> · changed {e.fields.join(", ")}</>}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </Sheet>
      {(page.more || before) && (
        <div className="mt-4 flex gap-2">
          {before && <LinkButton href={`/admin/audit${query({ action })}`} size="sm" variant="quiet">Newest</LinkButton>}
          {page.more && last && <LinkButton href={`/admin/audit${query({ action, before: last.id })}`} size="sm">Older</LinkButton>}
        </div>
      )}
    </>
  );
}
