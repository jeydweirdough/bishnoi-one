import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { SelectAllBox, SelectBox, SelectableRow, SelectionProvider } from "@/src/platform/bulk/selection";
import type { Assignable, CompanyRow, CustomerType, Paged } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { Filters, Pager } from "../components/crm/list-controls";
import { RecordsBulk } from "../components/crm/records-bulk";
import { StatusTag, typeOptions } from "../components/crm/words";
import { customFields } from "../components/extra/load";
import { extraText } from "../components/extra/extra-values";

export const metadata = { title: "Customers" };

const SIZE = 50;
type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function CompaniesPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.view")) return <NoAccess what="customers" />;
  const params = await searchParams;
  const [q, status, owner] = [one(params.q), one(params.status), one(params.owner)];
  const page = Math.max(1, Number(one(params.page)) || 1);
  const query = new URLSearchParams({ limit: String(SIZE), offset: String((page - 1) * SIZE) });
  if (q) query.set("q", q);
  if (status) query.set("status", status);
  if (owner) query.set("owner", owner);
  const bulk = { followUp: can(me, "activities.create"), edit: can(me, "customers.edit"), delete: can(me, "customers.delete") };
  const bulkAllowed = bulk.followUp || bulk.edit || bulk.delete;
  const [list, people, types, fields] = await Promise.all([
    load<Paged<CompanyRow>>(`/companies?${query}`),
    bulkAllowed ? load<Assignable[]>("/people/assignable") : Promise.resolve([] as Assignable[]),
    load<CustomerType[]>("/customer-types"),
    customFields("company"),
  ]);
  // Fields an admin added and chose to show in the list: under each name, after the industry.
  const inList = fields.filter((f) => f.inList);
  const fmt = makeFormat(me.org);
  const filtered = Boolean(q || status || owner);
  const here = new URLSearchParams({ ...(q && { q }), ...(status && { status }), ...(owner && { owner }) });

  return (
    <>
      <PageHeader
        title="Customers"
        actions={
          can(me, "customers.create") && (
            <LinkButton href="/companies/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add customer
            </LinkButton>
          )
        }
      >
        {list.total} {list.total === 1 ? "customer" : "customers"}
        {filtered ? " match" : ""}
        {me.role?.scope === "own" ? " of yours" : me.role?.scope === "team" ? " in your team" : ""}.
      </PageHeader>


      <Filters
        search="Search by name, city or industry"
        selects={[
          { name: "status", label: "Type", options: [{ value: "", label: "Any type" }, ...typeOptions(types)] },
          ...(me.role?.scope !== "own"
            ? [{ name: "owner", label: "Owner", options: [{ value: "", label: "Everyone you can see" }, { value: "me", label: "Mine" }] }]
            : []),
        ]}
      />

      <SelectionProvider key={here.toString() + page} items={list.items.filter((c) => c.can.edit || c.can.delete || bulk.followUp).map((c) => ({ id: c.id, name: c.name }))}>
        <Sheet>
          {list.items.length === 0 ? (
            <Empty
              icon="company"
              title={filtered ? "No customers match" : "No customers yet"}
              actions={
                filtered ? (
                  <LinkButton href="/companies">Clear filters</LinkButton>
                ) : (
                  can(me, "customers.create") && (
                    <LinkButton href="/companies/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
                      Add customer
                    </LinkButton>
                  )
                )
              }
            >
              {filtered ? "Try another search, or clear the filters." : "Add the organisations you sell to, then their people under Contacts."}
            </Empty>
          ) : (
            <>
              {bulkAllowed && (
                <div className="border-b border-rule px-5">
                  <SelectAllBox>
                    <span className="text-meta text-ink-3">Select all on this page</span>
                  </SelectAllBox>
                </div>
              )}
              <ul className="divide-y divide-rule">
                {list.items.map((c) => (
                  <SelectableRow key={c.id} id={c.id} as="li" className="flex items-center gap-3 px-5 hover:bg-bench/40">
                    {bulkAllowed && <SelectBox id={c.id} label={c.name} />}
                    <Link
                      href={`/companies/${c.id}`}
                      className="grid min-w-0 flex-1 gap-1 py-3 md:grid-cols-[minmax(0,1fr)_6.5rem_minmax(0,9rem)_minmax(0,9rem)_7rem] md:items-center md:gap-4"
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-semibold text-hema">{c.name}</span>
                        <span className="block truncate text-meta text-ink-3">
                          {[
                            c.industry,
                            `${c.contactCount} ${c.contactCount === 1 ? "contact" : "contacts"}`,
                            ...inList.map((f) => {
                              const v = extraText(fmt, f, c.extra[f.key]);
                              return v && `${f.label}: ${v}`;
                            }),
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </span>
                      <span>
                        <StatusTag status={c.status} types={types} />
                      </span>
                      <span className="truncate text-meta text-ink-2">{[c.city, c.country].filter(Boolean).join(", ") || "—"}</span>
                      <span className="truncate text-meta text-ink-2">{c.owner.id === me.user.id ? "You" : c.owner.name}</span>
                      <span className="text-meta text-ink-3">{c.lastActivityAt ? fmt.whenLabel(c.lastActivityAt) : "No activity"}</span>
                    </Link>
                  </SelectableRow>
                ))}
              </ul>
            </>
          )}
        </Sheet>
        {bulkAllowed && (
          <RecordsBulk kind="companies" types={types} can={bulk} people={people} filters={Object.fromEntries(here)} total={list.total} org={me.org} />
        )}
      </SelectionProvider>
      <Pager total={list.total} page={page} size={SIZE} base={`/companies${here.size ? `?${here}` : ""}`} />
    </>
  );
}
