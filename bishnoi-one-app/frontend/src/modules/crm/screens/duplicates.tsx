import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { DuplicatePairs } from "@/src/platform/lib/types";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { DuplicatePair } from "@/src/modules/crm/components/crm/duplicate-pair";

export const metadata = { title: "Possible duplicates" };

// Customers or contacts that look like the same one entered twice: same phone,
// same email, the same or a similar name. Each pair can be merged into one, or
// marked as different so it isn't offered again.
export default async function DuplicatesPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.edit")) return <NoAccess what="possible duplicates" />;
  const kind = (await searchParams).kind === "contact" ? "contact" : "company";
  const found = await load<DuplicatePairs>(`/duplicates?kind=${kind}`);
  const fmt = makeFormat(me.org);
  const mayMerge = can(me, "customers.delete");
  const updated = Object.fromEntries(found.pairs.flatMap((p) => [p.a, p.b]).map((r) => [r.id, fmt.whenLabel(r.updatedAt).toLowerCase()]));
  const noun = kind === "company" ? "customers" : "contacts";

  return (
    <>
      <PageHeader title="Possible duplicates" crumbs={[{ href: kind === "company" ? "/crm/companies" : "/crm/contacts", label: kind === "company" ? "Customers" : "Contacts" }]}>
        {kind === "company" ? "Customers" : "Contacts"} that look like one entered twice, most likely first.{" "}
        {mayMerge ? "Merge them into one, or mark them as not the same." : "Your role can't merge; ask your team lead or an administrator."}
      </PageHeader>
      <div className="mb-4">
        <ToggleLinks
          current={kind}
          options={[
            { value: "company", label: "Customers", href: "/crm/companies/duplicates" },
            { value: "contact", label: "Contacts", href: "/crm/companies/duplicates?kind=contact" },
          ]}
        />
      </div>
      <Sheet>
        {found.pairs.length === 0 ? (
          <div className="px-5 py-2">
            <Empty icon="customers" title={`No possible duplicate ${noun}`}>
              None of the {noun} you can see share a phone number or email, or have the same name.
            </Empty>
          </div>
        ) : (
          <>
            <p className="border-b border-rule px-5 py-2.5 text-meta text-ink-2">
              {found.total} {found.total === 1 ? "pair" : "pairs"}
              {found.total > found.pairs.length ? `; the first ${found.pairs.length} shown` : ""}.
            </p>
            <ul className="divide-y divide-rule">
              {found.pairs.map((p) => (
                <DuplicatePair key={`${p.a.id}-${p.b.id}`} kind={kind} a={p.a} b={p.b} reasons={p.reasons} score={p.score} mayMerge={mayMerge} updatedLabel={updated} />
              ))}
            </ul>
          </>
        )}
      </Sheet>
    </>
  );
}
