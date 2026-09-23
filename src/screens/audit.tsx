import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { AuditPage } from "@/src/platform/lib/types";

export const metadata = { title: "Audit log" };

// What each recorded change was, said plainly. Anything not listed reads from its code.
const ACTIONS: Record<string, string> = {
  "person.created": "Added a person",
  "person.added": "Added a person from another company",
  "person.updated": "Changed a person",
  "assignment.added": "Gave a role",
  "assignment.removed": "Took a role away",
  "roles.permissions_changed": "Changed what roles can do",
  "team.added": "Added a team",
  "team.updated": "Changed a team",
  "goals.changed": "Changed goal targets",
  "pricing.rules_changed": "Changed pricing rules",
  "price_type.added": "Added a price type",
  "price_type.updated": "Changed a price type",
  "issuer.added": "Added a guarantee letter issuer",
  "issuer.updated": "Changed a guarantee letter issuer",
  "retention.rules_changed": "Changed retention rules",
  "orders.list_changed": "Changed an order pick-list",
  "orders.fields_changed": "Changed the extra order fields",
  "orders.rules_changed": "Changed the order rules",
  "product.added": "Added a product",
  "product.updated": "Changed a product",
  "product.prices_changed": "Changed a product's prices",
  "promo.added": "Added a promo",
  "promo.changed": "Changed a promo",
  "promo.switched_on": "Switched a promo on",
  "promo.switched_off": "Switched a promo off",
  "customer.created": "Added a customer",
  "customer.updated": "Changed a customer",
  "customer.moved": "Moved a customer to another team",
  "customer.deleted": "Deleted a customer",
  "quote.created": "Made a quote",
  "quote.deleted": "Deleted a quote",
  "quote.approved": "Approved a quote",
  "quote.rejected": "Rejected a quote",
  "quote.letter_verified": "Verified a guarantee letter",
  "quote.letter_rejected": "Rejected a guarantee letter",
  "quote.payment_recorded": "Recorded a letter payment",
};

function describe(action: string): string {
  if (ACTIONS[action]) return ACTIONS[action];
  if (action.startsWith("bulk.")) return `Bulk action: ${action.split(".").slice(1).join(" ").replaceAll("_", " ")}`;
  return action.replaceAll(/[._]/g, " ");
}

export default async function AuditLogPage({ searchParams }: { params: Promise<Record<string, never>>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { before } = await searchParams;
  const [page, me] = await Promise.all([
    load<AuditPage>(`/admin/audit?limit=50${typeof before === "string" ? `&before=${enc(before)}` : ""}`),
    getCompanyMe(),
  ]);
  const when = new Intl.DateTimeFormat(me.org.locale, { dateStyle: "medium", timeStyle: "short", timeZone: me.org.timezone });
  const last = page.items.at(-1);

  return (
    <>
      <PageHeader title="Audit log">
        Who changed what, newest first. It names the fields that changed, never what they were changed to.
      </PageHeader>
      <Sheet className="px-5 pt-2 pb-3">
        {page.items.length === 0 ? (
          <Empty title={before ? "Nothing older" : "Nothing recorded yet"} icon="auditLog">
            Changes to people, roles, settings, products, customers and quotes show up here.
          </Empty>
        ) : (
          <ol className="divide-y divide-rule">
            {page.items.map((e) => (
              <li key={e.id} className="grid gap-x-4 gap-y-0.5 py-3 sm:grid-cols-[11rem_minmax(0,1fr)]">
                <time dateTime={e.at} className="text-meta text-ink-3 tabular-nums">
                  {when.format(new Date(e.at))}
                </time>
                <div className="min-w-0">
                  <p className="text-sm">
                    <span className="font-semibold">{describe(e.action)}</span>
                    {e.target && <span className="text-ink-2"> · {e.target}</span>}
                  </p>
                  <p className="text-meta text-ink-3">
                    by {e.actor}
                    {e.fields.length > 0 && <> · changed {e.fields.join(", ")}</>}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Sheet>
      {(page.more || before) && (
        <div className="mt-4 flex gap-2">
          {before && (
            <LinkButton href="/settings/audit" size="sm" variant="quiet">
              Newest
            </LinkButton>
          )}
          {page.more && last && (
            <LinkButton href={`/settings/audit?before=${enc(last.at)}`} size="sm">
              Older
            </LinkButton>
          )}
        </div>
      )}
    </>
  );
}
