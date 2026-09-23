import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { CompanyRow, Paged } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { Filters, Pager } from "../components/crm/list-controls";
import { STATUSES, StatusTag } from "../components/crm/words";

export const metadata = { title: "Companies" };

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
  const list = await load<Paged<CompanyRow>>(`/companies?${query}`);
  const fmt = makeFormat(me.org);
  const filtered = Boolean(q || status || owner);
  const here = new URLSearchParams({ ...(q && { q }), ...(status && { status }), ...(owner && { owner }) });

  return (
    <>
      <PageHeader
        title="Companies"
        actions={
          can(me, "customers.create") && (
            <LinkButton href="/companies/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add company
            </LinkButton>
          )
        }
      >
        {list.total} {list.total === 1 ? "company" : "companies"}
        {filtered ? " match" : ""}
        {me.role?.scope === "own" ? " of yours" : me.role?.scope === "team" ? " in your team" : ""}.
      </PageHeader>

      <Filters
        search="Search by name, city or industry"
        selects={[
          { name: "status", label: "Status", options: [{ value: "", label: "Any status" }, ...STATUSES] },
          ...(me.role?.scope !== "own"
            ? [{ name: "owner", label: "Owner", options: [{ value: "", label: "Everyone you can see" }, { value: "me", label: "Mine" }] }]
            : []),
        ]}
      />

      <Sheet>
        {list.items.length === 0 ? (
          <Empty icon="company" title={filtered ? "No companies match" : "No companies yet"}>
            {filtered ? "Try another search, or clear the filters." : "Add the organisations you sell to, then their people under Contacts."}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {list.items.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/companies/${c.id}`}
                  className="grid gap-1 px-5 py-3 hover:bg-bench/40 md:grid-cols-[minmax(0,1fr)_6.5rem_minmax(0,9rem)_minmax(0,9rem)_7rem] md:items-center md:gap-4"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-semibold text-hema">{c.name}</span>
                    <span className="block truncate text-meta text-ink-3">
                      {[c.industry, `${c.contactCount} ${c.contactCount === 1 ? "contact" : "contacts"}`].filter(Boolean).join(" · ")}
                    </span>
                  </span>
                  <span>
                    <StatusTag status={c.status} />
                  </span>
                  <span className="truncate text-meta text-ink-2">{[c.city, c.country].filter(Boolean).join(", ") || "—"}</span>
                  <span className="truncate text-meta text-ink-2">{c.owner.id === me.user.id ? "You" : c.owner.name}</span>
                  <span className="text-meta text-ink-3">{c.lastActivityAt ? fmt.whenLabel(c.lastActivityAt) : "No activity"}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
      <Pager total={list.total} page={page} size={SIZE} base={`/companies${here.size ? `?${here}` : ""}`} />
    </>
  );
}
